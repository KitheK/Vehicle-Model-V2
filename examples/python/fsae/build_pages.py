#!/usr/bin/env python3
"""Write Cloudflare static assets into ./public (HUD, MATLAB, Studio, index).

    PYTHONPATH=examples/python python examples/python/fsae/build_pages.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

from fsae.qss_job import DEFAULT_CAR, DEFAULT_MAP, run_qss_job  # noqa: E402

_INDEX = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta http-equiv="refresh" content="0; url=hud.html"/>
<title>UBCO 2026 FSAE EV2</title>
<link rel="canonical" href="hud.html"/>
</head>
<body>
<p><a href="hud.html">HUD</a> · <a href="results.html">MATLAB</a> · <a href="studio.html">Studio</a></p>
</body>
</html>
"""


def main() -> int:
    public = _ROOT / "public"
    tmp = Path(tempfile.mkdtemp(prefix="qss_pages_"))
    try:
        run_qss_job(
            DEFAULT_CAR,
            DEFAULT_MAP,
            tmp,
            synthetic=True,
            plots=False,
        )
        public.mkdir(parents=True, exist_ok=True)
        for name in ("hud.html", "results.html", "studio.html"):
            src = tmp / name
            if not src.is_file():
                raise SystemExit(f"missing {name} in QSS output")
            shutil.copyfile(src, public / name)
        (public / "index.html").write_text(_INDEX, encoding="utf-8")
        (public / "404.html").write_text(
            "<!DOCTYPE html><html lang='en'><meta charset='utf-8'/>"
            "<title>Not found</title><p>Not found. "
            "<a href='hud.html'>HUD</a></p></html>\n",
            encoding="utf-8",
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"Wrote {public}/hud.html")
    print(f"Wrote {public}/results.html")
    print(f"Wrote {public}/studio.html")
    print(f"Wrote {public}/index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
