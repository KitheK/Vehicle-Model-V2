"""Read an OpenTRACK-format workbook and emit a fastest-lap discrete circuit XML.

Workbook layout (same as OpenLAP / OpenTRACK Shape Data tmp.xlsx):

- Sheet ``Info``: Name, Country, City, Type, Configuration, Direction, Mirror
- Sheet ``Shape``: ``Type | Section Length | Corner Radius``
  Type is Straight / Left / Right. Radius 0 means a straight.
- Optional ``OfficialLine``: ``Longitude | Latitude`` (original WGS84 racing line)
- Optional ``Locations``: named sites ``Name | Role | Latitude | Longitude | Bearing_deg``
- Optional ``MapCorners``: ``Corner | Latitude | Longitude`` (tl/tr/bl)
- Optional Elevation / Banking / Grip Factors / Sectors (ignored for 2D XML).

The Shape polyline is the racing line (OpenLAP does not store corridor width).
A constant half-width is applied so fastest-lap has left/right limits.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.worksheet import Worksheet

SHAPE_HEADER = ("Type", "Section Length", "Corner Radius")
OFFICIAL_LINE_HEADER = ("Longitude", "Latitude")
LOCATIONS_HEADER = ("Name", "Role", "Latitude", "Longitude", "Bearing_deg")
MAP_CORNERS_HEADER = ("Corner", "Latitude", "Longitude")
R_EARTH_M = 6378137.0


@dataclass
class OpenTrackInfo:
    name: str = "Track"
    country: str = ""
    city: str = ""
    kind: str = "Temporary"
    configuration: str = "Closed"
    direction: str = "Forward"
    mirror: str = "Off"


@dataclass
class OpenTrackMesh:
    info: OpenTrackInfo
    s: List[float]
    x: List[float]
    y: List[float]
    yaw: List[float]
    kappa: List[float]
    nl: List[float]
    nr: List[float]

    @property
    def length(self) -> float:
        return float(self.s[-1]) if self.s else 0.0


@dataclass
class TrackLocation:
    name: str
    role: str  # original | alternate
    lat: float
    lon: float
    bearing_deg: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "lat": self.lat,
            "lon": self.lon,
            "bearingDeg": self.bearing_deg,
        }


@dataclass
class TrackGeoref:
    """WGS84 line + named sites stored inside a map workbook."""

    official_line: List[List[float]] = field(default_factory=list)  # [[lon, lat], ...]
    locations: List[TrackLocation] = field(default_factory=list)
    map_corners: Dict[str, List[float]] = field(default_factory=dict)  # tl/tr/bl → [lat, lon]

    def original(self) -> Optional[TrackLocation]:
        for loc in self.locations:
            if loc.role.lower() == "original":
                return loc
        return self.locations[0] if self.locations else None

    def find(self, name: str) -> Optional[TrackLocation]:
        key = name.strip().lower()
        for loc in self.locations:
            if loc.name.strip().lower() == key:
                return loc
        return None


def _cell_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip().strip('"')


def read_opentrack_info(path: str | Path) -> OpenTrackInfo:
    wb = load_workbook(path, data_only=True, read_only=True)
    try:
        ws = wb[wb.sheetnames[0] if "Info" not in wb.sheetnames else "Info"]
        kv = {}
        for row in ws.iter_rows(values_only=True):
            if not row or row[0] is None:
                continue
            kv[_cell_str(row[0]).lower()] = _cell_str(row[1] if len(row) > 1 else None)
    finally:
        wb.close()
    return OpenTrackInfo(
        name=kv.get("name") or Path(path).stem,
        country=kv.get("country", ""),
        city=kv.get("city", ""),
        kind=kv.get("type", "Temporary"),
        configuration=kv.get("configuration", "Closed"),
        direction=kv.get("direction", "Forward"),
        mirror=kv.get("mirror", "Off"),
    )


def read_opentrack_shape(path: str | Path) -> List[Tuple[str, float, float]]:
    wb = load_workbook(path, data_only=True, read_only=True)
    try:
        if "Shape" not in wb.sheetnames:
            raise ValueError(f"{path} has no 'Shape' sheet (OpenTRACK format).")
        rows: List[Tuple[str, float, float]] = []
        for i, row in enumerate(wb["Shape"].iter_rows(values_only=True), 1):
            if i == 1 or row is None or row[0] is None:
                continue
            kind = _cell_str(row[0]).title()
            length = float(row[1] or 0.0)
            radius = float(row[2] or 0.0)
            if length <= 0.0:
                continue
            rows.append((kind, length, radius))
    finally:
        wb.close()
    if not rows:
        raise ValueError(f"{path} Shape sheet has no segments.")
    return rows


def _segment_kappa(kind: str, radius: float, mirror_sign: float) -> float:
    if kind == "Left" and radius > 0.0:
        return mirror_sign / radius
    if kind == "Right" and radius > 0.0:
        return -mirror_sign / radius
    return 0.0


def _rebase_pose(
    s: List[float], x: List[float], y: List[float]
) -> Tuple[List[float], List[float], List[float]]:
    """Translate to start at origin and rotate so the first step heads +X."""
    if len(x) < 2:
        return s, x, y
    x0, y0 = x[0], y[0]
    yaw0 = math.atan2(y[1] - y[0], x[1] - x[0])
    c, sn = math.cos(-yaw0), math.sin(-yaw0)
    xr = [c * (xi - x0) - sn * (yi - y0) for xi, yi in zip(x, y)]
    yr = [sn * (xi - x0) + c * (yi - y0) for xi, yi in zip(x, y)]
    return s, xr, yr


def mesh_opentrack(
    path: str | Path,
    mesh_size: float = 1.0,
    half_width: float = 1.5,
    scale: float = 1.0,
) -> OpenTrackMesh:
    """Rebuild the OpenTRACK racing line at a uniform mesh (default 1 m).

    Each Shape segment is integrated at **constant κ** (straight or circular arc),
    matching MATLAB OpenTRACK / the endurance-map arc verify (~0.7 m vs PNG line).
    Closed tracks get a linear start/finish XY join; yaw/κ are recomputed from XY.

    ``scale`` uniformly scales plan geometry (section lengths and corner radii),
    so a 0.5 map is a half-size track for QSS dynamics (κ → κ/scale).
    """
    info = read_opentrack_info(path)
    segments = read_opentrack_shape(path)
    closed = info.configuration.lower().startswith("closed")
    sign = -1.0 if info.mirror.lower() == "on" else 1.0
    ms = max(float(mesh_size), 1.0e-6)
    sc = float(scale) if scale and scale > 0.0 else 1.0

    s: List[float] = [0.0]
    x: List[float] = [0.0]
    y: List[float] = [0.0]
    s_cur = 0.0
    x_cur = 0.0
    y_cur = 0.0
    yaw_cur = 0.0

    for kind, length, radius in segments:
        length = float(length) * sc
        radius = float(radius) * sc if radius > 0.0 else 0.0
        k = _segment_kappa(kind, radius, sign)
        n = max(1, int(round(length / ms)))
        ds = length / float(n)
        for _ in range(n):
            if abs(k) < 1.0e-12:
                x_cur += ds * math.cos(yaw_cur)
                y_cur += ds * math.sin(yaw_cur)
            else:
                dth = k * ds
                x_cur += (math.sin(yaw_cur + dth) - math.sin(yaw_cur)) / k
                y_cur += (-math.cos(yaw_cur + dth) + math.cos(yaw_cur)) / k
                yaw_cur += dth
            s_cur += ds
            s.append(s_cur)
            x.append(x_cur)
            y.append(y_cur)

    L = s_cur
    if closed and L > 0.0 and len(x) > 1:
        dx_close = x[0] - x[-1]
        dy_close = y[0] - y[-1]
        x = [xi + si / L * dx_close for xi, si in zip(x, s)]
        y = [yi + si / L * dy_close for yi, si in zip(y, s)]
        x[-1], y[-1] = x[0], y[0]

    if info.direction.lower() == "backward" and L > 0.0:
        s = [L - si for si in reversed(s)]
        x = list(reversed(x))
        y = list(reversed(y))

    s, x, y = _rebase_pose(s, x, y)
    yaw, kappa = _heading_kappa_from_xy(s, x, y, closed=closed)
    hw = float(half_width) * sc
    nl = [hw] * len(s)
    nr = [hw] * len(s)
    return OpenTrackMesh(info=info, s=s, x=x, y=y, yaw=yaw, kappa=kappa, nl=nl, nr=nr)


def _unique_samples(xp: Sequence[float], yp: Sequence[float]) -> Tuple[List[float], List[float]]:
    xs: List[float] = []
    ys: List[float] = []
    for x, y in zip(xp, yp):
        if xs and abs(x - xs[-1]) < 1.0e-12:
            ys[-1] = float(y)
            continue
        xs.append(float(x))
        ys.append(float(y))
    return xs, ys


def _wrap_pi(angle: float) -> float:
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle


def _heading_kappa_from_xy(
    s: Sequence[float], x: Sequence[float], y: Sequence[float], closed: bool
) -> Tuple[List[float], List[float]]:
    n = len(s)
    heading = [0.0] * n
    for i in range(n - 1):
        heading[i] = math.atan2(y[i + 1] - y[i], x[i + 1] - x[i])
    heading[-1] = heading[0] if closed and n > 1 else heading[-2] if n > 1 else 0.0
    for i in range(1, n):
        heading[i] = heading[i - 1] + _wrap_pi(heading[i] - heading[i - 1])
    kappa = [0.0] * n
    for i in range(1, n):
        kappa[i] = (heading[i] - heading[i - 1]) / max(s[i] - s[i - 1], 1.0e-12)
    if closed and n > 1:
        kappa[0] = kappa[-1]
    return heading, kappa


def _interp(xp: Sequence[float], yp: Sequence[float], x: float) -> float:
    if x <= xp[0]:
        return float(yp[0])
    if x >= xp[-1]:
        return float(yp[-1])
    for i in range(len(xp) - 1):
        if xp[i] <= x <= xp[i + 1]:
            t = 0.0 if xp[i + 1] == xp[i] else (x - xp[i]) / (xp[i + 1] - xp[i])
            return float(yp[i] + t * (yp[i + 1] - yp[i]))
    return float(yp[-1])


def _csv(values: Sequence[float], digits: int = 8) -> str:
    return ", ".join(f"{v:.{digits}g}" for v in values)


def mesh_to_discrete_xml(mesh: OpenTrackMesh) -> str:
    n = len(mesh.s)
    nx = [-math.sin(h) for h in mesh.yaw]
    ny = [math.cos(h) for h in mesh.yaw]
    lx = [xi + nli * nxi for xi, nli, nxi in zip(mesh.x, mesh.nl, nx)]
    ly = [yi + nli * nyi for yi, nli, nyi in zip(mesh.y, mesh.nl, ny)]
    rx = [xi - nri * nxi for xi, nri, nxi in zip(mesh.x, mesh.nr, nx)]
    ry = [yi - nri * nyi for yi, nri, nyi in zip(mesh.y, mesh.nr, ny)]
    dyaw = [0.0] + [
        (mesh.kappa[i] - mesh.kappa[i - 1]) / max(mesh.s[i] - mesh.s[i - 1], 1.0e-12)
        for i in range(1, n)
    ]
    zeros = [0.0] * n
    closed = "closed" if mesh.info.configuration.lower().startswith("closed") else "open"
    return f"""<circuit format="discrete" type="{closed}" dimensions="2">
    <header>
        <track_length units="m">{mesh.length:.8g}</track_length>
        <L2_error_left>0</L2_error_left>
        <L2_error_right>0</L2_error_right>
        <max_error_left>0</max_error_left>
        <max_error_right>0</max_error_right>
    </header>
    <optimization>
        <cost_curvature>10.000000</cost_curvature>
        <cost_track_limits_smoothness>0.000100</cost_track_limits_smoothness>
        <cost_track_limits_errors>0.000100</cost_track_limits_errors>
        <cost_centerline>0.000100</cost_centerline>
        <maximum_yaw_dot>4.000000</maximum_yaw_dot>
        <maximum_dyaw_dot>4.000000</maximum_dyaw_dot>
    </optimization>
    <GPS_parameters>
        <origin_longitude units="deg">0</origin_longitude>
        <origin_latitude units="deg">0</origin_latitude>
        <earth_radius units="m">6378388</earth_radius>
        <reference_latitude units="deg">0</reference_latitude>
    </GPS_parameters>
    <data number_of_points="{n}">
        <arclength units="m">{_csv(mesh.s)}</arclength>
        <centerline>
            <x units="m">{_csv(mesh.x)}</x>
            <y units="m">{_csv(mesh.y)}</y>
        </centerline>
        <left_boundary>
            <x units="m">{_csv(lx)}</x>
            <y units="m">{_csv(ly)}</y>
        </left_boundary>
        <right_boundary>
            <x units="m">{_csv(rx)}</x>
            <y units="m">{_csv(ry)}</y>
        </right_boundary>
        <left_measured_boundary>
            <x units="m">{_csv(lx)}</x>
            <y units="m">{_csv(ly)}</y>
        </left_measured_boundary>
        <right_measured_boundary>
            <x units="m">{_csv(rx)}</x>
            <y units="m">{_csv(ry)}</y>
        </right_measured_boundary>
        <yaw units="rad">{_csv(mesh.yaw)}</yaw>
        <yaw_dot units="rad">{_csv(mesh.kappa)}</yaw_dot>
        <nl units="m">{_csv(mesh.nl)}</nl>
        <nr units="m">{_csv(mesh.nr)}</nr>
        <dyaw_dot>{_csv(dyaw)}</dyaw_dot>
        <dnl>{_csv(zeros)}</dnl>
        <dnr>{_csv(zeros)}</dnr>
    </data>
</circuit>
"""


def _header_index(header: Sequence[Any], *names: str) -> Optional[int]:
    lower = [str(c or "").strip().lower() for c in header]
    for name in names:
        key = name.lower()
        if key in lower:
            return lower.index(key)
    return None


def read_official_line(path: str | Path) -> List[List[float]]:
    """Return [[lon, lat], ...] from the OfficialLine sheet (empty if missing)."""
    wb = load_workbook(path, data_only=True, read_only=True)
    try:
        if "OfficialLine" not in wb.sheetnames:
            return []
        rows = list(wb["OfficialLine"].iter_rows(values_only=True))
    finally:
        wb.close()
    if not rows:
        return []
    header = rows[0]
    i_lon = _header_index(header, "longitude", "lon", "lng")
    i_lat = _header_index(header, "latitude", "lat")
    if i_lon is None or i_lat is None:
        return []
    out: List[List[float]] = []
    for row in rows[1:]:
        if not row or row[i_lon] is None or row[i_lat] is None:
            continue
        out.append([float(row[i_lon]), float(row[i_lat])])
    return out


def list_track_locations(path: str | Path) -> List[TrackLocation]:
    """Queryable named sites from the Locations sheet."""
    wb = load_workbook(path, data_only=True, read_only=True)
    try:
        if "Locations" not in wb.sheetnames:
            return []
        rows = list(wb["Locations"].iter_rows(values_only=True))
    finally:
        wb.close()
    if not rows:
        return []
    header = rows[0]
    i_name = _header_index(header, "name")
    i_role = _header_index(header, "role")
    i_lat = _header_index(header, "latitude", "lat")
    i_lon = _header_index(header, "longitude", "lon", "lng")
    i_brg = _header_index(header, "bearing_deg", "bearing", "bearingdeg")
    if i_name is None or i_lat is None or i_lon is None:
        return []
    out: List[TrackLocation] = []
    for row in rows[1:]:
        if not row or row[i_name] is None:
            continue
        role = _cell_str(row[i_role] if i_role is not None else None, "alternate") or "alternate"
        brg = float(row[i_brg] or 0.0) if i_brg is not None else 0.0
        out.append(
            TrackLocation(
                name=_cell_str(row[i_name]),
                role=role.lower(),
                lat=float(row[i_lat]),
                lon=float(row[i_lon]),
                bearing_deg=brg,
            )
        )
    return out


def read_map_corners(path: str | Path) -> Dict[str, List[float]]:
    """Return {tl|tr|bl: [lat, lon]} from MapCorners sheet."""
    wb = load_workbook(path, data_only=True, read_only=True)
    try:
        if "MapCorners" not in wb.sheetnames:
            return {}
        rows = list(wb["MapCorners"].iter_rows(values_only=True))
    finally:
        wb.close()
    if not rows:
        return {}
    header = rows[0]
    i_c = _header_index(header, "corner", "name")
    i_lat = _header_index(header, "latitude", "lat")
    i_lon = _header_index(header, "longitude", "lon", "lng")
    if i_c is None or i_lat is None or i_lon is None:
        return {}
    out: Dict[str, List[float]] = {}
    for row in rows[1:]:
        if not row or row[i_c] is None:
            continue
        key = _cell_str(row[i_c]).lower()
        if key in ("tl", "tr", "bl"):
            out[key] = [float(row[i_lat]), float(row[i_lon])]
    return out


def read_track_georef(path: str | Path) -> Optional[TrackGeoref]:
    """Load OfficialLine + Locations (+ optional MapCorners) from a map workbook."""
    line = read_official_line(path)
    locs = list_track_locations(path)
    corners = read_map_corners(path)
    if len(line) < 2 and not locs:
        return None
    return TrackGeoref(official_line=line, locations=locs, map_corners=corners)


def _enu(lat: float, lon: float, lat0: float, lon0: float) -> Tuple[float, float]:
    e = math.radians(lon - lon0) * R_EARTH_M * math.cos(math.radians(lat0))
    n = math.radians(lat - lat0) * R_EARTH_M
    return e, n


def _from_enu(e: float, n: float, lat0: float, lon0: float) -> Tuple[float, float]:
    lat = lat0 + math.degrees(n / R_EARTH_M)
    lon = lon0 + math.degrees(e / (R_EARTH_M * math.cos(math.radians(lat0))))
    return lat, lon


def project_official_line(
    line_lonlat: Sequence[Sequence[float]],
    origin: TrackLocation,
    target: TrackLocation,
    scale: float = 1.0,
) -> List[List[float]]:
    """Move [[lon,lat],…] from origin to target; optional bearing + uniform scale."""
    if not line_lonlat:
        return []
    sc = float(scale) if scale and scale > 0 else 1.0
    same_pose = (
        origin.name == target.name
        and abs(origin.lat - target.lat) < 1e-12
        and abs(origin.lon - target.lon) < 1e-12
        and abs(target.bearing_deg - origin.bearing_deg) < 1e-12
    )
    if same_pose and abs(sc - 1.0) < 1e-12:
        return [[float(p[0]), float(p[1])] for p in line_lonlat]
    dbrg = math.radians(target.bearing_deg - origin.bearing_deg)
    c, s = math.cos(dbrg), math.sin(dbrg)
    out: List[List[float]] = []
    for p in line_lonlat:
        lon, lat = float(p[0]), float(p[1])
        e, n = _enu(lat, lon, origin.lat, origin.lon)
        e *= sc
        n *= sc
        er = c * e - s * n
        nr = s * e + c * n
        la, lo = _from_enu(er, nr, target.lat, target.lon)
        out.append([lo, la])
    return out


def write_georef_sheets(wb: Workbook, georef: TrackGeoref) -> None:
    """Append/replace OfficialLine, Locations, MapCorners on an open workbook."""
    for name in ("OfficialLine", "Locations", "MapCorners"):
        if name in wb.sheetnames:
            del wb[name]
    if georef.official_line:
        ws = wb.create_sheet("OfficialLine")
        ws.append(list(OFFICIAL_LINE_HEADER))
        for lon, lat in georef.official_line:
            ws.append([float(lon), float(lat)])
    if georef.locations:
        ws = wb.create_sheet("Locations")
        ws.append(list(LOCATIONS_HEADER))
        for loc in georef.locations:
            ws.append([loc.name, loc.role, loc.lat, loc.lon, loc.bearing_deg])
    if georef.map_corners:
        ws = wb.create_sheet("MapCorners")
        ws.append(list(MAP_CORNERS_HEADER))
        for key in ("tl", "tr", "bl"):
            if key in georef.map_corners:
                lat, lon = georef.map_corners[key]
                ws.append([key, float(lat), float(lon)])


def write_map_xlsx(
    path: str | Path,
    info: OpenTrackInfo | dict,
    shape: Sequence[Tuple[str, float, float]],
    georef: TrackGeoref | None = None,
) -> Path:
    """Write a Map workbook (Info + Shape [+ geo sheets]). Used by Studio and tests."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(info, OpenTrackInfo):
        meta = info
    else:
        meta = OpenTrackInfo(
            name=str(info.get("name") or "Track"),
            country=str(info.get("country") or ""),
            city=str(info.get("city") or ""),
            kind=str(info.get("type") or info.get("kind") or "Temporary"),
            configuration=str(info.get("configuration") or "Closed"),
            direction=str(info.get("direction") or "Forward"),
            mirror=str(info.get("mirror") or "Off"),
        )
    wb = Workbook()
    ws = wb.active
    ws.title = "Info"
    for row in (
        ("Name", meta.name),
        ("Country", meta.country),
        ("City", meta.city),
        ("Type", meta.kind),
        ("Configuration", meta.configuration),
        ("Direction", meta.direction),
        ("Mirror", meta.mirror),
    ):
        ws.append(list(row))
    sh = wb.create_sheet("Shape")
    sh.append(list(SHAPE_HEADER))
    for kind, length, radius in shape:
        sh.append([str(kind), float(length), float(radius)])
    if georef is not None:
        write_georef_sheets(wb, georef)
    from fsae.xlsx_kit import stamp_format

    stamp_format(wb, "map")
    wb.save(path)
    return path


def stamp_georef_into_xlsx(path: str | Path, georef: TrackGeoref) -> Path:
    """Add/replace OfficialLine + Locations (+ MapCorners) on an existing map workbook."""
    path = Path(path)
    wb = load_workbook(path)
    try:
        write_georef_sheets(wb, georef)
        wb.save(path)
    finally:
        wb.close()
    return path


def write_discrete_xml(xlsx_path: str | Path, xml_path: str | Path, **kwargs) -> Path:
    xml_path = Path(xml_path)
    xml_path.parent.mkdir(parents=True, exist_ok=True)
    xml_path.write_text(mesh_to_discrete_xml(mesh_opentrack(xlsx_path, **kwargs)), encoding="utf-8")
    return xml_path


def write_fsae_skidpad_xlsx(path: str | Path) -> Path:
    """FSAE figure-8 skidpad: two 9.125 m radius circles (OpenTRACK Shape layout)."""
    return write_map_xlsx(
        path,
        OpenTrackInfo(name="FSAE Skidpad", country="Greece", city="Athens"),
        (
            ("Left", 1, 9.125),
            ("Left", 55, 9.125),
            ("Left", 1, 9.125),
            ("Right", 1, 9.125),
            ("Right", 55, 9.125),
            ("Right", 1, 9.125),
        ),
    )
