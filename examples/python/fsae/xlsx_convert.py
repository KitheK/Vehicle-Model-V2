#!/usr/bin/env python3
"""Convert standard FSAE .xlsx workbooks (Car, Map, or Driver).

Car  → fastest-lap vehicle XML
Map  → fastest-lap discrete track XML
Driver → validated (already the lap-channel workbook)

    python examples/python/fsae/xlsx_convert.py database/vehicles/fsae/ubco-2026-ev.xlsx
    python examples/python/fsae/xlsx_convert.py database/tracks/fsae_2019_endurance/2019_endurance.xlsx
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

from fsae.xlsx_kit import convert_xlsx, detect_kind  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xlsx", type=Path, help="Car, Map, or Driver workbook")
    parser.add_argument("-o", "--output", type=Path, default=None)
    args = parser.parse_args()
    if not args.xlsx.is_file():
        parser.error(f"workbook not found: {args.xlsx}")
    kind = detect_kind(args.xlsx)
    out = convert_xlsx(args.xlsx, args.output)
    print(f"{kind}: {args.xlsx} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
