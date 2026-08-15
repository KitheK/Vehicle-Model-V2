#!/usr/bin/env python3
"""Convert an OpenTRACK-format workbook into fastest-lap discrete circuit XML.

    python3 examples/python/fsae/xlsx_to_track.py path/to/track.xlsx -o database/tracks/name/name.xml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

from fsae.opentrack_xlsx import write_discrete_xml, write_fsae_skidpad_xlsx  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xlsx", type=Path, help="OpenTRACK-format .xlsx workbook")
    parser.add_argument("-o", "--output", type=Path, default=None)
    parser.add_argument("--mesh-size", type=float, default=1.0)
    parser.add_argument("--half-width", type=float, default=1.5, help="Corridor half-width [m]")
    parser.add_argument(
        "--write-skidpad-template",
        action="store_true",
        help="Write the FSAE Skidpad OpenTRACK workbook to XLSX and exit",
    )
    args = parser.parse_args()
    if args.write_skidpad_template:
        write_fsae_skidpad_xlsx(args.xlsx)
        print(f"Wrote template {args.xlsx}")
        return 0
    if not args.xlsx.is_file():
        parser.error(f"workbook not found: {args.xlsx}")
    out = args.output or args.xlsx.with_suffix(".xml")
    write_discrete_xml(args.xlsx, out, mesh_size=args.mesh_size, half_width=args.half_width)
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
