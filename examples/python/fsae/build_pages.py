#!/usr/bin/env python3
"""Write Cloudflare static assets into ./public (HUD, MATLAB, Studio, runtime).

    PYTHONPATH=examples/python python examples/python/fsae/build_pages.py
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

from fsae.qss_job import DEFAULT_CAR, DEFAULT_MAP, defaults_payload, run_qss_job  # noqa: E402

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

_RUNTIME_PY = (
    "__init__.py",
    "qss_browser.py",
    "qss_job.py",
    "qss_lap.py",
    "qss_channels.py",
    "qss_viz.py",
    "xlsx_kit.py",
    "opentrack_xlsx.py",
    "openvehicle_xlsx.py",
    "qss_hud.html",
    "qss_results.html",
    "qss_studio.html",
)


def pack_runtime(public: Path) -> Path:
    zpath = public / "qss-runtime.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in _RUNTIME_PY:
            src = _HERE / name
            if src.is_file():
                zf.write(src, f"app/examples/python/fsae/{name}")
        for src, dest in (
            (DEFAULT_CAR, "app/database/vehicles/fsae/ubco-2026-ev.xlsx"),
            (DEFAULT_CAR.with_suffix(".xml"), "app/database/vehicles/fsae/ubco-2026-ev.xml"),
            (DEFAULT_MAP, "app/database/tracks/fsae_2019_endurance/2019_endurance.xlsx"),
        ):
            if src.is_file():
                zf.write(src, dest)
    return zpath


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
        shutil.copyfile(_HERE / "qss_studio.html", public / "studio.html")
        (public / "index.html").write_text(_INDEX, encoding="utf-8")
        (public / "defaults.json").write_text(
            json.dumps(defaults_payload(tmp), default=str),
            encoding="utf-8",
        )
        pack_runtime(public)
        car = public / "car.glb"
        src_car = _HERE / "models" / "formula_student.glb"
        if not car.is_file() and src_car.is_file():
            shutil.copyfile(src_car, car)
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
    print(f"Wrote {public}/defaults.json")
    print(f"Wrote {public}/qss-runtime.zip")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
