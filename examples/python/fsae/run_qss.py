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
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

from fsae.qss_job import DEFAULT_CAR, DEFAULT_MAP, DEFAULT_XML, run_qss_job  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vehicle-xlsx", type=Path, default=DEFAULT_CAR)
    parser.add_argument("--vehicle-xml", type=Path, default=DEFAULT_XML)
    parser.add_argument("--track-xlsx", type=Path, default=DEFAULT_MAP)
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

    summary = run_qss_job(
        args.vehicle_xlsx,
        args.track_xlsx,
        args.output,
        vehicle_xml=args.vehicle_xml,
        synthetic=args.synthetic or not args.vehicle_xml.is_file(),
        v_cap=args.v_cap,
        gg_speed=args.speed,
        gg_points=args.gg_points,
        cam_height=args.cam_height,
        plots=True,
        hud_index=args.hud_index,
    )
    print(f"Lap time {summary['lap_time']:.3f} s  ({summary['source']})")
    print(f"Wrote {args.output}/openlap_results.png")
    print(f"Wrote {args.output}/hud_frame.png")
    print(f"Wrote {args.output}/hud.html")
    print(f"Wrote {args.output}/results.html")
    print(f"Wrote {args.output}/channels.csv")
    print(f"Wrote {args.output}/driver.xlsx")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
