"""Georeference helpers: map-frame / WGS84 ↔ OpenLAP mesh XY for the HUD ground.

The EV 2026 endurance centreline CSV is in official-map metres (origin at
start/finish). ``mesh_opentrack`` rebuilds a similar closed line in its own
mesh frame. A rigid Kabsch transform (rotation + translation) aligns them so
satellite tiles and geojson circuits can be drawn under the QSS car.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

R_EARTH_M = 6378137.0

# Same as MAPCORNERS in fsae-ev-endurance-map/data.js (lat, lon)
MAP_TL = (42.0702476, -84.2359031)
MAP_TR = (42.0631343, -84.2382035)
MAP_BL = (42.0704515, -84.2370469)


def wrap_pi(a: float) -> float:
    while a > math.pi:
        a -= 2.0 * math.pi
    while a < -math.pi:
        a += 2.0 * math.pi
    return a


def enu(lat: float, lon: float, lat0: float, lon0: float) -> tuple[float, float]:
    x = math.radians(lon - lon0) * R_EARTH_M * math.cos(math.radians(lat0))
    y = math.radians(lat - lat0) * R_EARTH_M
    return x, y


def map_basis(
    tl: tuple[float, float] = MAP_TL,
    tr: tuple[float, float] = MAP_TR,
    bl: tuple[float, float] = MAP_BL,
) -> dict[str, float]:
    plat = (tl[0] + tr[0] + bl[0]) / 3.0
    plon = (tl[1] + tr[1] + bl[1]) / 3.0
    e_tl, n_tl = enu(*tl, plat, plon)
    e_tr, n_tr = enu(*tr, plat, plon)
    e_bl, n_bl = enu(*bl, plat, plon)
    rx, ry = e_tr - e_tl, n_tr - n_tl
    dx, dy = e_bl - e_tl, n_bl - n_tl
    right_len = math.hypot(rx, ry)
    down_len = math.hypot(dx, dy)
    rxx, rxy = rx / right_len, ry / right_len
    ux, uy = -dx / down_len, -dy / down_len
    return {
        "e_tl": e_tl,
        "n_tl": n_tl,
        "rxx": rxx,
        "rxy": rxy,
        "ux": ux,
        "uy": uy,
        "right_len": right_len,
        "down_len": down_len,
        "plat": plat,
        "plon": plon,
        "origin_lat": tl[0],
        "origin_lon": tl[1],
    }


def wgs84_to_map_xy(lat: float, lon: float, basis: dict[str, float]) -> tuple[float, float]:
    e, n = enu(lat, lon, basis["plat"], basis["plon"])
    de, dn = e - basis["e_tl"], n - basis["n_tl"]
    return de * basis["rxx"] + dn * basis["rxy"], de * basis["ux"] + dn * basis["uy"]


def map_xy_to_wgs84(mx: float, my: float, basis: dict[str, float]) -> tuple[float, float]:
    """Inverse of wgs84_to_map_xy (map metres from TL → lat/lon)."""
    de = mx * basis["rxx"] + my * basis["ux"]
    dn = mx * basis["rxy"] + my * basis["uy"]
    e = basis["e_tl"] + de
    n = basis["n_tl"] + dn
    lat = basis["plat"] + math.degrees(n / R_EARTH_M)
    lon = basis["plon"] + math.degrees(e / (R_EARTH_M * math.cos(math.radians(basis["plat"]))))
    return lat, lon


def load_centerline_csv(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    s = np.array([float(r["s_m"]) for r in rows], dtype=float)
    x = np.array([float(r["x_m"]) for r in rows], dtype=float)
    y = np.array([float(r["y_m"]) for r in rows], dtype=float)
    return s, x, y


def _resample_closed(x: np.ndarray, y: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray]:
    """Uniform arc-length resample of a nearly-closed polyline (drop duplicate end)."""
    if len(x) < 2:
        return x.copy(), y.copy()
    if math.hypot(float(x[0] - x[-1]), float(y[0] - y[-1])) < 1e-6:
        x, y = x[:-1], y[:-1]
    xc = np.r_[x, x[0]]
    yc = np.r_[y, y[0]]
    seg = np.hypot(np.diff(xc), np.diff(yc))
    s = np.concatenate([[0.0], np.cumsum(seg)])
    L = float(s[-1])
    if L < 1e-9:
        return np.zeros(n), np.zeros(n)
    st = np.linspace(0.0, L, n, endpoint=False)
    xr = np.interp(st, s, xc)
    yr = np.interp(st, s, yc)
    return xr, yr


def kabsch_2d(src: np.ndarray, dst: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Rigid transform dst ≈ R @ src + t. Returns R (2x2), t (2,), rms."""
    assert src.shape == dst.shape and src.shape[1] == 2
    c_src = src.mean(axis=0)
    c_dst = dst.mean(axis=0)
    A = src - c_src
    B = dst - c_dst
    H = A.T @ B
    U, _, Vt = np.linalg.svd(H)
    R = Vt.T @ U.T
    if np.linalg.det(R) < 0:
        Vt[-1, :] *= -1
        R = Vt.T @ U.T
    t = c_dst - R @ c_src
    fitted = (R @ src.T).T + t
    rms = float(np.sqrt(np.mean(np.sum((fitted - dst) ** 2, axis=1))))
    return R, t, rms


def align_map_to_mesh(
    map_x: np.ndarray,
    map_y: np.ndarray,
    mesh_x: Sequence[float],
    mesh_y: Sequence[float],
    samples: int = 400,
) -> dict[str, Any]:
    """Compute rigid map→mesh transform from two closed centrelines."""
    mx, my = _resample_closed(np.asarray(map_x, float), np.asarray(map_y, float), samples)
    hx, hy = _resample_closed(np.asarray(mesh_x, float), np.asarray(mesh_y, float), samples)
    # Try both orientations (map may be reverse of mesh direction)
    src = np.column_stack([mx, my])
    dst = np.column_stack([hx, hy])
    R1, t1, rms1 = kabsch_2d(src, dst)
    R2, t2, rms2 = kabsch_2d(src[::-1].copy(), dst)
    if rms2 < rms1:
        R, t, rms = R2, t2, rms2
        reversed_map = True
    else:
        R, t, rms = R1, t1, rms1
        reversed_map = False
    return {
        "R": R.tolist(),
        "t": t.tolist(),
        "rms_m": rms,
        "reversed_map": reversed_map,
        "samples": samples,
    }


def map_to_mesh(xy: np.ndarray, R: np.ndarray, t: np.ndarray) -> np.ndarray:
    """Apply rigid transform. xy shape (N,2) or (2,)."""
    single = xy.ndim == 1
    pts = np.atleast_2d(xy)
    out = (R @ pts.T).T + t
    return out[0] if single else out


def mesh_to_map(xy: np.ndarray, R: np.ndarray, t: np.ndarray) -> np.ndarray:
    single = xy.ndim == 1
    pts = np.atleast_2d(xy)
    out = (np.linalg.inv(R) @ (pts - t).T).T
    return out[0] if single else out


def build_georef(
    mesh_x: Sequence[float],
    mesh_y: Sequence[float],
    centerline_csv: Path,
    pad_m: float = 40.0,
) -> dict[str, Any]:
    s, cx, cy = load_centerline_csv(centerline_csv)
    # CSV is already origin-at-S/F map metres
    align = align_map_to_mesh(cx, cy, mesh_x, mesh_y)
    R = np.array(align["R"], float)
    t = np.array(align["t"], float)
    basis = map_basis()
    hx = np.asarray(mesh_x, float)
    hy = np.asarray(mesh_y, float)
    bbox = {
        "x0": float(hx.min() - pad_m),
        "y0": float(hy.min() - pad_m),
        "x1": float(hx.max() + pad_m),
        "y1": float(hy.max() + pad_m),
    }
    # Start/finish lat/lon from first CSV row if present — else map TL shifted
    return {
        "track": "fsae_ev_2026_endurance",
        "origin_lat": basis["plat"],
        "origin_lon": basis["plon"],
        "map_corners": {"tl": list(MAP_TL), "tr": list(MAP_TR), "bl": list(MAP_BL)},
        "map_basis": {k: float(v) for k, v in basis.items()},
        "R": align["R"],
        "t": align["t"],
        "rms_m": align["rms_m"],
        "reversed_map": align["reversed_map"],
        "bbox_mesh_m": bbox,
        "centerline_length_m": float(s[-1]) if len(s) else 0.0,
        "mesh_length_m": float(
            np.sum(np.hypot(np.diff(hx, append=hx[0]), np.diff(hy, append=hy[0])))
        ),
        "notes": "map_xy (official PNG frame, S/F origin) → mesh_xy via R,t; WGS84 via map_basis",
    }


def save_georef(path: Path, georef: dict[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(georef, indent=2), encoding="utf-8")
    return path


def load_georef(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def mesh_north_angle_rad(georef: dict[str, Any]) -> float:
    """Angle of geographic north in OpenLAP mesh XY (atan2 of a +N EN step).

    Leaflet endurance-map is north-up. HUD drawTrack rotates by
    ``π/2 - mesh_north_angle`` so mesh north matches screen up.
    """
    basis = georef["map_basis"]
    R = np.array(georef["R"], float)
    t = np.array(georef["t"], float)
    plat = float(basis["plat"])
    plon = float(basis["plon"])

    def en_to_mesh(e: float, n: float) -> np.ndarray:
        lat = plat + math.degrees(n / R_EARTH_M)
        lon = plon + math.degrees(e / (R_EARTH_M * math.cos(math.radians(plat))))
        mx, my = wgs84_to_map_xy(lat, lon, basis)
        return map_to_mesh(np.array([mx, my], float), R, t)

    d = en_to_mesh(0.0, 100.0) - en_to_mesh(0.0, 0.0)
    return float(math.atan2(float(d[1]), float(d[0])))


def transform_lonlat_lines(
    coords_lonlat: Iterable[Sequence[float]],
    georef: dict[str, Any],
    sf_origin_map: tuple[float, float] | None = None,
) -> list[list[float]]:
    """Convert GeoJSON [lon,lat] vertices to mesh XY.

    ``sf_origin_map`` is the map-frame position of start/finish before the CSV
    recentre (usually the first official-line point in map metres from TL).
    If None, assumes coords are already relative to the same origin as the CSV
    after subtracting the first point — callers should pass map_xy of S/F.
    """
    basis = georef["map_basis"]
    R = np.array(georef["R"], float)
    t = np.array(georef["t"], float)
    out: list[list[float]] = []
    ox, oy = sf_origin_map if sf_origin_map is not None else (0.0, 0.0)
    for lon, lat in coords_lonlat:
        mx, my = wgs84_to_map_xy(lat, lon, basis)
        mx -= ox
        my -= oy
        mesh = map_to_mesh(np.array([mx, my]), R, t)
        out.append([float(mesh[0]), float(mesh[1])])
    return out
