#!/usr/bin/env python3
"""Local Studio server: upload Car/Map/Driver xlsx, edit UBCO defaults, run QSS.

    python examples/python/fsae/qss_server.py --port 18080
    # open http://127.0.0.1:18080/studio.html
"""

from __future__ import annotations

import argparse
import email.parser
import email.policy
import json
import shutil
import sys
import tempfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Tuple
from urllib.parse import urlparse

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

from fsae.opentrack_xlsx import write_map_xlsx  # noqa: E402
from fsae.qss_job import DEFAULT_CAR, DEFAULT_MAP, defaults_payload, run_qss_job  # noqa: E402
from fsae.xlsx_kit import detect_kind, patch_car_xlsx, preview_workbook  # noqa: E402

MAX_BODY = 25 * 1024 * 1024


def _parse_multipart(content_type: str, body: bytes) -> Tuple[Dict[str, str], Dict[str, Tuple[str, bytes]]]:
    preamble = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode()
    msg = email.parser.BytesParser(policy=email.policy.default).parsebytes(preamble + body)
    fields: Dict[str, str] = {}
    files: Dict[str, Tuple[str, bytes]] = {}
    for part in msg.iter_parts():
        disp = part.get("Content-Disposition", "")
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename:
            files[str(name)] = (str(filename), payload)
        else:
            fields[str(name)] = payload.decode("utf-8", errors="replace")
        _ = disp
    return fields, files


def _save_upload(tmp: Path, name: str, payload: bytes) -> Path:
    path = tmp / name
    path.write_bytes(payload)
    return path


class StudioHandler(SimpleHTTPRequestHandler):
    out_dir: Path = Path("qss_out")

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send_json(self, data: Any, code: int = 200) -> None:
        raw = json.dumps(data, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _send_bytes(self, data: bytes, content_type: str, code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, path: Path, content_type: str, cache: str = "no-store") -> None:
        size = path.stat().st_size
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        with path.open("rb") as fh:
            shutil.copyfileobj(fh, self.wfile, length=1024 * 1024)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/", "/studio.html"):
            html = (_HERE / "qss_studio.html").read_bytes()
            self._send_bytes(html, "text/html; charset=utf-8")
            return
        if path == "/api/defaults":
            self._send_json(defaults_payload(self.out_dir))
            return
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if path == "/car.glb":
            for cand in (
                _ROOT / "public" / "car.glb",
                _HERE / "models" / "formula_student.glb",
                _HERE / "car.glb",
                self.out_dir / "car.glb",
                Path(r"c:\Users\USER\Downloads\car model 3d\formula_student.glb"),
            ):
                if cand.is_file():
                    self._send_file(cand, "model/gltf-binary", cache="public, max-age=3600")
                    return
            self.send_error(404, "car.glb not found")
            return
        rel = path.lstrip("/")
        for folder in (self.out_dir, _ROOT / "public"):
            candidate = folder / rel
            if candidate.is_file() and candidate.resolve().is_relative_to(folder.resolve()):
                ctype = self.guess_type(str(candidate)) or "application/octet-stream"
                self._send_file(candidate, ctype)
                return
        self.send_error(404, "Not found")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            self._send_json({"error": "upload too large"}, 413)
            return
        body = self.rfile.read(length)
        ctype = self.headers.get("Content-Type") or ""
        try:
            fields, files = _parse_multipart(ctype, body)
        except Exception as exc:
            self._send_json({"error": f"bad multipart: {exc}"}, 400)
            return
        if parsed.path == "/api/preview":
            try:
                self._send_json(self._preview(fields, files))
            except Exception as exc:
                self._send_json({"error": str(exc)}, 400)
            return
        if parsed.path != "/api/run":
            self.send_error(404, "Not found")
            return
        try:
            result = self._run(fields, files)
        except Exception as exc:
            self._send_json({"error": str(exc)}, 400)
            return
        self._send_json(result)

    def _preview(self, fields: Dict[str, str], files: Dict[str, Tuple[str, bytes]]) -> Dict[str, Any]:
        blob_pair = files.get("file") or files.get("map") or files.get("car") or files.get("driver")
        if not blob_pair or not blob_pair[1]:
            raise ValueError("choose a .xlsx file to process")
        name, blob = blob_pair
        tmp = Path(tempfile.mkdtemp(prefix="qss_preview_"))
        try:
            path = _save_upload(tmp, name or "upload.xlsx", blob)
            data = preview_workbook(path)
            expect = (fields.get("expect") or "").strip().lower()
            if expect and data["kind"] != expect:
                raise ValueError(f"that workbook is a {data['kind']} file, not a {expect} file")
            return data
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def _run(self, fields: Dict[str, str], files: Dict[str, Tuple[str, bytes]]) -> Dict[str, Any]:
        tmp = Path(tempfile.mkdtemp(prefix="qss_studio_"))
        try:
            car_src = DEFAULT_CAR
            map_src = DEFAULT_MAP
            driver_src = None
            if "car" in files and files["car"][1]:
                name, blob = files["car"]
                car_up = _save_upload(tmp, name or "car.xlsx", blob)
                if detect_kind(car_up) != "car":
                    raise ValueError("uploaded car file is not a Car workbook")
                car_src = car_up
            if "map" in files and files["map"][1]:
                name, blob = files["map"]
                map_up = _save_upload(tmp, name or "map.xlsx", blob)
                if detect_kind(map_up) != "map":
                    raise ValueError("uploaded map file is not a Map workbook (need Info + Shape)")
                map_src = map_up
            if "driver" in files and files["driver"][1]:
                name, blob = files["driver"]
                driver_up = _save_upload(tmp, name or "driver.xlsx", blob)
                if detect_kind(driver_up) != "driver":
                    raise ValueError("uploaded driver file is not a Driver workbook")
                driver_src = driver_up

            overrides = json.loads(fields.get("overrides") or "[]")
            car_xlsx = tmp / "car.xlsx"
            # Same rule for cars: an upload wins; otherwise patch the default from the editor.
            if "car" in files and files["car"][1]:
                shutil.copyfile(car_src, car_xlsx)
            else:
                patch_car_xlsx(car_src, car_xlsx, overrides)

            map_xlsx = map_src
            # An uploaded Map workbook is the source of truth. The editor Shape table
            # is only written when the user did not attach a map file.
            if not ("map" in files and files["map"][1]) and fields.get("shape"):
                from fsae.opentrack_xlsx import OpenTrackInfo

                info_raw = json.loads(fields.get("map_info") or "{}")
                shape_raw = json.loads(fields["shape"])
                shape = [
                    (str(s.get("type") or "Straight"), float(s.get("length") or 0), float(s.get("radius") or 0))
                    for s in shape_raw
                    if float(s.get("length") or 0) > 0
                ]
                if not shape:
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
                write_map_xlsx(map_xlsx, info, shape)

            synthetic = str(fields.get("synthetic") or "true").lower() not in {"0", "false", "no"}
            v_cap = float(fields.get("v_cap") or 40.0)
            cam_height = float(fields.get("cam_height") or 80.0)
            self.out_dir.mkdir(parents=True, exist_ok=True)
            return run_qss_job(
                car_xlsx,
                map_xlsx,
                self.out_dir,
                driver_xlsx=driver_src,
                synthetic=synthetic,
                v_cap=v_cap,
                cam_height=cam_height,
                plots=False,
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18080)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("-o", "--output", type=Path, default=_ROOT / "qss_out")
    args = parser.parse_args()
    StudioHandler.out_dir = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    httpd = ThreadingHTTPServer((args.bind, args.port), StudioHandler)
    print(f"Studio http://{args.bind}:{args.port}/studio.html")
    print(f"Artifacts {StudioHandler.out_dir}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
