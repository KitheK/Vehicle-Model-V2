#!/usr/bin/env python3
"""Run an OpenLAP-style QSS lap and write OpenLAP + fastest-lap HUD artifacts.

    python3 examples/python/fsae/run_qss.py \\
        --vehicle-xlsx database/vehicles/fsae/ubco-2026-ev.xlsx \\
        --vehicle-xml  database/vehicles/fsae/ubco-2026-ev.xml \\
        --track-xlsx   database/tracks/fsae_2019_endurance/2019_endurance.xlsx \\
        -o /tmp/qss_out
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

from fsae.opentrack_xlsx import mesh_opentrack  # noqa: E402
from fsae.openvehicle_xlsx import derived_vehicle, read_openvehicle_xlsx  # noqa: E402
from fsae.qss_channels import reconstruct_lap, write_csv  # noqa: E402
from fsae.qss_lap import GGTable, build_gg_table, qss_lap  # noqa: E402
from fsae.qss_viz import plot_hud_frame, plot_openlap_results, write_hud_html, write_summary  # noqa: E402


def _synthetic_table() -> GGTable:
    ay = [0.0, 0.5, 1.0, 1.5, 1.65]
    ax_max = [0.50, 0.42, 0.30, 0.12, 0.0]
    ax_min = [-0.90, -0.82, -0.65, -0.30, 0.0]
    return GGTable(speeds=[15.0], ay=[ay], ax_max=[ax_max], ax_min=[ax_min])


def _load_gg(vehicle_xml: Path, speed: float, n_points: int) -> GGTable:
    os.environ.setdefault("LD_LIBRARY_PATH", "")
    import fastest_lap

    name = "fsae_qss_car"
    try:
        fastest_lap.create_vehicle_from_xml(name, str(vehicle_xml))
    except Exception:
        pass
    return build_gg_table(name, [speed], n_points=n_points)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vehicle-xlsx", type=Path, default=_ROOT / "database/vehicles/fsae/ubco-2026-ev.xlsx")
    parser.add_argument("--vehicle-xml", type=Path, default=_ROOT / "database/vehicles/fsae/ubco-2026-ev.xml")
    parser.add_argument(
        "--track-xlsx",
        type=Path,
        default=_ROOT / "database/tracks/fsae_2019_endurance/2019_endurance.xlsx",
    )
    parser.add_argument("-o", "--output", type=Path, default=Path("qss_out"))
    parser.add_argument("--speed", type=float, default=15.0, help="G-G envelope speed [m/s]")
    parser.add_argument("--gg-points", type=int, default=10)
    parser.add_argument("--v-cap", type=float, default=40.0)
    parser.add_argument("--synthetic", action="store_true", help="Skip fastest-lap gg_diagram (tests / no lib)")
    parser.add_argument("--hud-index", type=int, default=None, help="Mesh index for the static HUD PNG")
    parser.add_argument("--cam-height", type=float, default=80.0, help="Follow-cam vertical field [m]")
    args = parser.parse_args()

    if not args.track_xlsx.is_file():
        parser.error(f"track workbook not found: {args.track_xlsx}")
    mesh = mesh_opentrack(args.track_xlsx)
    params = {}
    if args.vehicle_xlsx.is_file():
        params = derived_vehicle(read_openvehicle_xlsx(args.vehicle_xlsx))

    if args.synthetic or not args.vehicle_xml.is_file():
        table = _synthetic_table()
        source = "synthetic G-G"
    else:
        table = _load_gg(args.vehicle_xml, args.speed, args.gg_points)
        source = f"fastest-lap gg_diagram at {args.speed:.1f} m/s"

    result = qss_lap(mesh, table, v_cap=args.v_cap)
    view = reconstruct_lap(
        result,
        mesh,
        table,
        params=params,
        vehicle_name=str(params.get("name") or "FSAE"),
        track_name=mesh.info.name,
    )
    view.notes = source + ". " + view.notes

    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    plot_openlap_results(view, out / "openlap_results.png")
    plot_hud_frame(view, out / "hud_frame.png", index=args.hud_index, cam_height=args.cam_height)
    write_hud_html(view, out / "hud.html", cam_height=args.cam_height)
    write_csv(view, out / "channels.csv")
    write_summary(view, out / "summary.txt")
    print(f"Lap time {view.lap_time:.3f} s  ({source})")
    print(f"Wrote {out}/openlap_results.png")
    print(f"Wrote {out}/hud_frame.png")
    print(f"Wrote {out}/hud.html")
    print(f"Wrote {out}/channels.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
