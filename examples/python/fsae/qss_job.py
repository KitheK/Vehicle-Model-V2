"""Run a QSS lap from Car / Map / Driver workbooks (CLI and Studio)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from fsae.opentrack_xlsx import mesh_opentrack
from fsae.openvehicle_xlsx import derived_vehicle, read_openvehicle_xlsx, write_xml
from fsae.qss_channels import reconstruct_lap, write_csv
from fsae.qss_lap import GGTable, build_gg_table, qss_lap
from fsae.xlsx_kit import gg_from_driver_xlsx, write_driver_xlsx
from fsae.qss_viz import write_hud_html, write_results_html, write_summary

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
DEFAULT_CAR = _ROOT / "database/vehicles/fsae/ubco-2026-ev.xlsx"
DEFAULT_XML = _ROOT / "database/vehicles/fsae/ubco-2026-ev.xml"
DEFAULT_MAP = _ROOT / "database/tracks/fsae_2019_endurance/2019_endurance.xlsx"


def synthetic_gg() -> GGTable:
    ay = [0.0, 0.5, 1.0, 1.5, 1.65]
    return GGTable(
        speeds=[15.0],
        ay=[ay],
        ax_max=[[0.50, 0.42, 0.30, 0.12, 0.0]],
        ax_min=[[-0.90, -0.82, -0.65, -0.30, 0.0]],
    )


def _load_gg(vehicle_xml: Path, speed: float, n_points: int) -> GGTable:
    os.environ.setdefault("LD_LIBRARY_PATH", "")
    import fastest_lap

    name = "fsae_qss_car"
    try:
        fastest_lap.create_vehicle_from_xml(name, str(vehicle_xml))
    except Exception:
        pass
    return build_gg_table(name, [speed], n_points=n_points)


def run_qss_job(
    vehicle_xlsx: Path,
    track_xlsx: Path,
    output: Path,
    vehicle_xml: Optional[Path] = None,
    driver_xlsx: Optional[Path] = None,
    synthetic: bool = True,
    v_cap: float = 40.0,
    gg_speed: float = 15.0,
    gg_points: int = 10,
    cam_height: float = 80.0,
    plots: bool = False,
    hud_index: Optional[int] = None,
) -> Dict[str, Any]:
    """Mesh the map, reconstruct driver/6DOF channels, write HUD + MATLAB pages."""
    mesh = mesh_opentrack(track_xlsx)
    params: Dict[str, Any] = {}
    if vehicle_xlsx.is_file():
        params = derived_vehicle(read_openvehicle_xlsx(vehicle_xlsx))

    table = None
    source = "synthetic G-G"
    if driver_xlsx and Path(driver_xlsx).is_file():
        table = gg_from_driver_xlsx(driver_xlsx)
        if table is not None:
            source = "Driver Envelope G-G"
    if table is None:
        xml = vehicle_xml if vehicle_xml is not None else vehicle_xlsx.with_suffix(".xml")
        if synthetic or not Path(xml).is_file():
            table = synthetic_gg()
            source = "synthetic G-G"
        else:
            table = _load_gg(Path(xml), gg_speed, gg_points)
            source = f"fastest-lap gg_diagram at {gg_speed:.1f} m/s"

    result = qss_lap(mesh, table, v_cap=v_cap)
    view = reconstruct_lap(
        result,
        mesh,
        table,
        params=params,
        vehicle_name=str(params.get("name") or "FSAE"),
        track_name=mesh.info.name,
    )
    view.notes = source + ". " + view.notes

    output.mkdir(parents=True, exist_ok=True)
    if plots:
        from fsae.qss_viz import plot_hud_frame, plot_openlap_results

        plot_openlap_results(view, output / "openlap_results.png")
        plot_hud_frame(view, output / "hud_frame.png", index=hud_index, cam_height=cam_height)
    write_hud_html(view, output / "hud.html", cam_height=cam_height)
    write_results_html(view, output / "results.html", cam_height=cam_height)
    write_csv(view, output / "channels.csv")
    write_driver_xlsx(view, output / "driver.xlsx")
    write_summary(view, output / "summary.txt")
    studio = Path(__file__).resolve().parent / "qss_studio.html"
    if studio.is_file():
        (output / "studio.html").write_bytes(studio.read_bytes())
    if vehicle_xlsx.is_file():
        try:
            write_xml(vehicle_xlsx, output / "vehicle.xml")
        except Exception:
            pass

    v_kmh = [x * 3.6 for x in view.v]
    return {
        "lap_time": view.lap_time,
        "vehicle": view.vehicle_name,
        "track": view.track_name,
        "source": source,
        "notes": view.notes,
        "n": len(view.s),
        "length_m": view.s[-1] if view.s else 0.0,
        "speed_kmh": {
            "min": min(v_kmh) if v_kmh else 0.0,
            "mean": sum(v_kmh) / len(v_kmh) if v_kmh else 0.0,
            "max": max(v_kmh) if v_kmh else 0.0,
        },
        "peak_ay_g": max(abs(a) for a in view.ay) if view.ay else 0.0,
        "files": {
            "hud": "hud.html",
            "results": "results.html",
            "driver": "driver.xlsx",
            "channels": "channels.csv",
        },
    }


def defaults_payload(output: Optional[Path] = None) -> Dict[str, Any]:
    from fsae.opentrack_xlsx import read_opentrack_info, read_opentrack_shape
    from fsae.xlsx_kit import list_car_fields, read_driver_xlsx

    car_fields = list_car_fields(DEFAULT_CAR) if DEFAULT_CAR.is_file() else []
    map_info = {}
    shape: Sequence = []
    length = 0.0
    if DEFAULT_MAP.is_file():
        info = read_opentrack_info(DEFAULT_MAP)
        map_info = {
            "name": info.name,
            "country": info.country,
            "city": info.city,
            "type": info.kind,
            "configuration": info.configuration,
            "direction": info.direction,
            "mirror": info.mirror,
        }
        shape = [{"type": k, "length": L, "radius": r} for k, L, r in read_opentrack_shape(DEFAULT_MAP)]
        length = sum(s["length"] for s in shape)
    driver: Dict[str, Any] = {"present": False}
    driver_path = (output or Path("qss_out")) / "driver.xlsx"
    if driver_path.is_file():
        data = read_driver_xlsx(driver_path)
        driver = {"present": True, **{k: data["info"].get(k) for k in data["info"]}}
        driver["samples"] = len(data["channels"].get("distance_m") or [])
    return {
        "car": {"name": next((f["value"] for f in car_fields if f["description"] == "Name"), "UBCO 2026 EV"),
                "path": str(DEFAULT_CAR), "fields": car_fields},
        "map": {"path": str(DEFAULT_MAP), "info": map_info, "shape": shape, "length_m": length},
        "driver": driver,
        "settings": {"v_cap": 40.0, "synthetic": True, "cam_height": 80.0},
    }
