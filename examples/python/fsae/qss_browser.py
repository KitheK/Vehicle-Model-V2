"""Studio preview/run helpers shared by the local server and the Cloudflare browser runtime."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from fsae.opentrack_xlsx import OpenTrackInfo, write_map_xlsx
from fsae.qss_job import DEFAULT_CAR, DEFAULT_MAP, run_qss_job
from fsae.xlsx_kit import detect_kind, patch_car_xlsx, preview_workbook


def preview_path(path: str | Path, expect: str = "") -> Dict[str, Any]:
    data = preview_workbook(path)
    expect = (expect or "").strip().lower()
    if expect and data["kind"] != expect:
        raise ValueError(f"that workbook is a {data['kind']} file, not a {expect} file")
    return data


def run_studio(
    *,
    car_path: Optional[str | Path] = None,
    map_path: Optional[str | Path] = None,
    driver_path: Optional[str | Path] = None,
    overrides: Any = None,
    map_info: Any = None,
    shape: Any = None,
    v_cap: float = 40.0,
    synthetic: bool = True,
    cam_height: float = 80.0,
    output: Optional[str | Path] = None,
) -> Dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="qss_studio_"))
    out = Path(output) if output is not None else tmp / "out"
    try:
        car_src = Path(car_path) if car_path else DEFAULT_CAR
        map_src = Path(map_path) if map_path else DEFAULT_MAP
        driver_src = Path(driver_path) if driver_path else None
        if car_path and detect_kind(car_src) != "car":
            raise ValueError("uploaded car file is not a Car workbook")
        if map_path and detect_kind(map_src) != "map":
            raise ValueError("uploaded map file is not a Map workbook (need Info + Shape)")
        if driver_src is not None and detect_kind(driver_src) != "driver":
            raise ValueError("uploaded driver file is not a Driver workbook")

        if isinstance(overrides, str):
            overrides = json.loads(overrides or "[]")
        overrides = overrides or []

        car_xlsx = tmp / "car.xlsx"
        if car_path:
            shutil.copyfile(car_src, car_xlsx)
        else:
            patch_car_xlsx(car_src, car_xlsx, overrides)

        map_xlsx = map_src
        if not map_path and shape:
            if isinstance(map_info, str):
                map_info = json.loads(map_info or "{}")
            if isinstance(shape, str):
                shape = json.loads(shape)
            info_raw = map_info or {}
            segments = [
                (str(s.get("type") or "Straight"), float(s.get("length") or 0), float(s.get("radius") or 0))
                for s in shape
                if float(s.get("length") or 0) > 0
            ]
            if not segments:
                raise ValueError("map Shape has no segments")
            info = OpenTrackInfo(
                name=str(info_raw.get("name") or "Track"),
                country=str(info_raw.get("country") or ""),
                city=str(info_raw.get("city") or ""),
                kind=str(info_raw.get("type") or "Temporary"),
                configuration=str(info_raw.get("configuration") or "Closed"),
                direction=str(info_raw.get("direction") or "Forward"),
                mirror=str(info_raw.get("mirror") or "Off"),
            )
            map_xlsx = tmp / "map.xlsx"
            write_map_xlsx(map_xlsx, info, segments)

        out.mkdir(parents=True, exist_ok=True)
        summary = run_qss_job(
            car_xlsx,
            map_xlsx,
            out,
            driver_xlsx=driver_src,
            synthetic=synthetic,
            v_cap=float(v_cap),
            cam_height=float(cam_height),
            plots=False,
        )
        summary["hud_html"] = (out / "hud.html").read_text(encoding="utf-8")
        summary["results_html"] = (out / "results.html").read_text(encoding="utf-8")
        return summary
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
