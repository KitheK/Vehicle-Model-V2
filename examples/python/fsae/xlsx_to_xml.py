#!/usr/bin/env python3
"""Convert an OpenVEHICLE-format vehicle workbook into fastest-lap XML.

The workbook follows the OpenLAP / OpenVEHICLE layout used by UBCO's
Vehicle_Model (Info + Torque Curve sheets). An optional FastestLap sheet
holds 6DOF-only numbers that OpenVEHICLE does not define.

    python3 examples/python/fsae/xlsx_to_xml.py database/vehicles/fsae/ubco-2026-ev.xlsx \\
        -o database/vehicles/fsae/ubco-2026-ev.xml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

from fsae.openvehicle_xlsx import write_ubco_2026_xlsx, write_xml  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xlsx", type=Path, help="OpenVEHICLE-format .xlsx workbook")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output XML path (default: same stem as the workbook)",
    )
    parser.add_argument(
        "--write-template",
        action="store_true",
        help="Write a filled UBCO 2026 OpenVEHICLE template to XLSX and exit",
    )
    args = parser.parse_args()

    if args.write_template:
        write_ubco_2026_xlsx(args.xlsx)
        print(f"Wrote template {args.xlsx}")
        return 0

    if not args.xlsx.is_file():
        parser.error(f"workbook not found: {args.xlsx}")

    out = args.output or args.xlsx.with_suffix(".xml")
    write_xml(args.xlsx, out)
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
