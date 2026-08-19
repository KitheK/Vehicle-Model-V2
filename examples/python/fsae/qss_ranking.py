"""Save, rank, export, and downsample QSS car setups."""

from __future__ import annotations

import json
import re
import uuid
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from fsae.xlsx_kit import detect_kind, patch_car_xlsx

MAX_POINTS = 400
MAX_RECORD_BYTES = 200_000
LAP_KEYS = (
    "s",
    "x",
    "y",
    "time",
    "v",
    "vmax",
    "kappa",
    "ax",
    "ay",
    "tps",
    "bps",
    "steer",
    "delta",
    "beta",
)
GHOST_KEYS = ("s", "x", "y", "v", "time")
SORT_KEYS = (
    "lap_time",
    "speed_min",
    "speed_mean",
    "speed_max",
    "peak_ay_g",
    "mass",
    "maximum_power",
    "saved_at",
)


def field_value(fields: Sequence[Dict[str, Any]], description: str) -> Any:
    want = description.strip().lower()
    for item in fields:
        if str(item.get("description") or "").strip().lower() == want:
            return item.get("value")
    return None


def field_float(fields: Sequence[Dict[str, Any]], description: str) -> Optional[float]:
    raw = field_value(fields, description)
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def downsample_aligned(arrays: Dict[str, Sequence[float]], max_points: int = MAX_POINTS) -> Dict[str, List[float]]:
    """Keep channel indices aligned; no-op when already short."""
    usable = {k: list(v) for k, v in arrays.items() if v is not None}
    if not usable:
        return {}
    n = min(len(v) for v in usable.values())
    if n <= 0:
        return {k: [] for k in usable}
    if n <= max_points:
        return {k: [float(x) for x in v[:n]] for k, v in usable.items()}
    step = (n - 1) / (max_points - 1)
    idx = [min(n - 1, int(round(i * step))) for i in range(max_points)]
    return {k: [float(v[i]) for i in idx] for k, v in usable.items()}


def channels_from_view(view: Any, max_points: int = MAX_POINTS) -> Dict[str, Any]:
    """Compact MATLAB/HUD channels from a LapView."""
    lap = downsample_aligned(
        {
            "s": view.s,
            "x": view.x,
            "y": view.y,
            "time": view.time,
            "v": view.v,
            "vmax": getattr(view, "v_max", []),
            "kappa": view.kappa,
            "ax": view.ax,
            "ay": view.ay,
            "tps": view.tps,
            "bps": view.bps,
            "steer": view.steer,
            "delta": view.delta,
            "beta": view.beta,
        },
        max_points=max_points,
    )
    lap["envAy"] = [float(x) for x in (view.env_ay or [])]
    lap["envAxMax"] = [float(x) for x in (view.env_ax_max or [])]
    lap["envAxMin"] = [float(x) for x in (view.env_ax_min or [])]
    lap["envSpeed"] = float(getattr(view, "env_speed", 0.0) or 0.0)
    lap["vehicle"] = str(view.vehicle_name)
    lap["track"] = str(view.track_name)
    lap["lapTime"] = float(view.lap_time)
    return lap


def ghost_from_channels(channels: Dict[str, Any]) -> Dict[str, List[float]]:
    return {k: list(channels.get(k) or []) for k in GHOST_KEYS}


def matlab_from_channels(channels: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {k: list(channels.get(k) or []) for k in LAP_KEYS}
    for key in ("envAy", "envAxMax", "envAxMin"):
        out[key] = list(channels.get(key) or [])
    out["envSpeed"] = float(channels.get("envSpeed") or 0.0)
    out["vehicle"] = channels.get("vehicle") or ""
    out["track"] = channels.get("track") or ""
    out["lapTime"] = float(channels.get("lapTime") or channels.get("lap_time") or 0.0)
    return out


def slug(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", str(text).strip()).strip("-").lower()
    return cleaned or "setup"


def filename_for(entry: Dict[str, Any]) -> str:
    return f"{slug(entry.get('name') or 'setup')}_{slug(entry.get('map') or 'map')}.xlsx"


def load_entries(path: str | Path) -> List[Dict[str, Any]]:
    path = Path(path)
    if not path.is_file():
        return []
    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"corrupt ranking.json: {exc}") from exc
    if not isinstance(data, list):
        raise ValueError("ranking.json must be a JSON list")
    return data


def write_entries(path: str | Path, entries: Sequence[Dict[str, Any]]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(list(entries), default=str), encoding="utf-8")
    return path


def sort_entries(entries: Sequence[Dict[str, Any]], key: str = "lap_time", reverse: bool = False) -> List[Dict[str, Any]]:
    if key not in SORT_KEYS:
        key = "lap_time"

    def value(entry: Dict[str, Any]) -> Any:
        if key == "speed_min":
            return (entry.get("speed_kmh") or {}).get("min")
        if key == "speed_mean":
            return (entry.get("speed_kmh") or {}).get("mean")
        if key == "speed_max":
            return (entry.get("speed_kmh") or {}).get("max")
        if key == "mass":
            return entry.get("car", {}).get("mass")
        if key == "maximum_power":
            return entry.get("car", {}).get("maximum_power")
        return entry.get(key)

    missing = 1e99 if not reverse else ""

    def sort_item(entry: Dict[str, Any]) -> Any:
        val = value(entry)
        return missing if val is None else val

    return sorted(entries, key=sort_item, reverse=reverse)


def filter_by_map(entries: Sequence[Dict[str, Any]], map_name: Optional[str]) -> List[Dict[str, Any]]:
    if not map_name or map_name == "All maps":
        return list(entries)
    return [e for e in entries if e.get("map") == map_name]


def default_map_filter(entries: Sequence[Dict[str, Any]]) -> str:
    if not entries:
        return "All maps"
    latest = max(entries, key=lambda e: str(e.get("saved_at") or ""))
    return str(latest.get("map") or "All maps")


def find_by_name(entries: Sequence[Dict[str, Any]], name: str) -> Optional[Dict[str, Any]]:
    for entry in entries:
        if entry.get("name") == name:
            return entry
    return None


def find_by_id(entries: Sequence[Dict[str, Any]], entry_id: str) -> Optional[Dict[str, Any]]:
    for entry in entries:
        if entry.get("id") == entry_id:
            return entry
    return None


def _trim_record(entry: Dict[str, Any]) -> Dict[str, Any]:
    blob = json.dumps(entry, default=str)
    if len(blob.encode("utf-8")) <= MAX_RECORD_BYTES:
        return entry
    matlab = dict(entry.get("matlab") or {})
    lap = {k: matlab.get(k) or [] for k in LAP_KEYS}
    smaller = downsample_aligned({k: v for k, v in lap.items() if v}, max_points=220)
    matlab.update(smaller)
    entry = dict(entry)
    entry["matlab"] = matlab
    entry["ghost"] = ghost_from_channels(matlab)
    return entry


def build_record(
    *,
    name: str,
    summary: Dict[str, Any],
    car_fields: Sequence[Dict[str, Any]],
    channels: Optional[Dict[str, Any]] = None,
    v_cap: float = 40.0,
    synthetic: bool = True,
    entry_id: Optional[str] = None,
    saved_at: Optional[str] = None,
) -> Dict[str, Any]:
    name = str(name or "").strip()
    if not name:
        raise ValueError("name is required")
    fields = [dict(f) for f in car_fields]
    channels = dict(channels or summary.get("channels") or {})
    matlab = matlab_from_channels(channels)
    if not matlab.get("lapTime"):
        matlab["lapTime"] = float(summary.get("lap_time") or 0.0)
    if not matlab.get("vehicle"):
        matlab["vehicle"] = str(summary.get("vehicle") or "")
    if not matlab.get("track"):
        matlab["track"] = str(summary.get("track") or "")
    entry = {
        "id": entry_id or str(uuid.uuid4()),
        "name": name,
        "saved_at": saved_at or datetime.now(timezone.utc).isoformat(),
        "map": str(summary.get("track") or matlab.get("track") or ""),
        "vehicle": str(summary.get("vehicle") or matlab.get("vehicle") or ""),
        "lap_time": float(summary.get("lap_time") or matlab.get("lapTime") or 0.0),
        "speed_kmh": dict(summary.get("speed_kmh") or {}),
        "peak_ay_g": float(summary.get("peak_ay_g") or 0.0),
        "v_cap": float(v_cap),
        "synthetic": bool(synthetic),
        "car": {
            "mass": field_float(fields, "Total Mass"),
            "maximum_power": field_float(fields, "Maximum Power"),
            "fields": fields,
        },
        "ghost": ghost_from_channels(matlab),
        "matlab": matlab,
    }
    if not entry["speed_kmh"] and matlab.get("v"):
        kmh = [float(v) * 3.6 for v in matlab["v"]]
        entry["speed_kmh"] = {
            "min": min(kmh),
            "mean": sum(kmh) / len(kmh),
            "max": max(kmh),
        }
    if not entry["peak_ay_g"] and matlab.get("ay"):
        entry["peak_ay_g"] = max(abs(float(a)) for a in matlab["ay"])
    return _trim_record(entry)


def save_entry(path: str | Path, record: Dict[str, Any], overwrite: bool = False) -> Dict[str, Any]:
    entries = load_entries(path)
    existing = find_by_name(entries, record["name"])
    if existing is not None:
        if not overwrite:
            raise ValueError(f"a setup named {record['name']!r} already exists")
        record = dict(record)
        record["id"] = existing["id"]
        entries = [e for e in entries if e.get("id") != existing["id"]]
    entries.append(record)
    write_entries(path, entries)
    return record


def delete_entry(path: str | Path, entry_id: str) -> bool:
    entries = load_entries(path)
    kept = [e for e in entries if e.get("id") != entry_id]
    if len(kept) == len(entries):
        return False
    write_entries(path, kept)
    return True


def export_car_xlsx(
    entry: Dict[str, Any],
    dest: str | Path,
    template: Optional[str | Path] = None,
) -> Path:
    if template is None:
        from fsae.qss_job import DEFAULT_CAR
        template = DEFAULT_CAR
    template = Path(template)
    if not template.is_file():
        raise FileNotFoundError("UBCO car template not found")
    fields = list((entry.get("car") or {}).get("fields") or [])
    name = entry.get("name")
    patched = False
    overrides = []
    for item in fields:
        item = dict(item)
        if str(item.get("description") or "").strip().lower() == "name" and item.get("sheet") == "Info":
            item["value"] = name
            patched = True
        overrides.append(item)
    if not patched:
        overrides.append({"sheet": "Info", "description": "Name", "value": name})
    dest = Path(dest)
    patch_car_xlsx(template, dest, overrides)
    if detect_kind(dest) != "car":
        raise ValueError("exported workbook is not a Car file")
    return dest


def export_zip(entries: Iterable[Dict[str, Any]], dest: str | Path, template: Optional[str | Path] = None) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        used = set()
        for entry in entries:
            name = filename_for(entry)
            base, suf = name, 1
            while name in used:
                name = filename_for(entry).replace(".xlsx", f"-{suf}.xlsx")
                suf += 1
            used.add(name)
            buf = BytesIO()
            tmp = dest.parent / f".tmp-{entry.get('id')}.xlsx"
            try:
                export_car_xlsx(entry, tmp, template=template)
                zf.writestr(name, tmp.read_bytes())
            finally:
                if tmp.is_file():
                    tmp.unlink()
            _ = buf
    return dest
