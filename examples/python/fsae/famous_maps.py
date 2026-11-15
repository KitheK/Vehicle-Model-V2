"""Catalog of famous racing lines (WGS84) for the QSS HUD map picker."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

_HERE = Path(__file__).resolve().parent
_FAMOUS_DIR = _HERE.parents[2] / "database" / "tracks" / "famous_maps"

# Display order for the HUD Map dropdown.
FAMOUS_MAP_FILES: list[tuple[str, str, Path]] = [
    ("ev_2026", "FSAE EV 2026 Endurance", _FAMOUS_DIR / "ev_2026.geojson"),
    ("ic_2026", "FSAE IC 2026 Endurance", _FAMOUS_DIR / "ic_2026.geojson"),
    ("spa", "Spa-Francorchamps", _FAMOUS_DIR / "spa.geojson"),
    ("monaco", "Circuit de Monaco", _FAMOUS_DIR / "monaco.geojson"),
    ("silverstone", "Silverstone", _FAMOUS_DIR / "silverstone.geojson"),
    ("monza", "Monza", _FAMOUS_DIR / "monza.geojson"),
    ("catalunya", "Circuit de Catalunya", _FAMOUS_DIR / "catalunya.geojson"),
    ("suzuka", "Suzuka", _FAMOUS_DIR / "suzuka.geojson"),
]


def _line_from_geojson(data: dict) -> tuple[list[list[float]], dict]:
    feats = data.get("features")
    if isinstance(feats, list) and feats:
        geom = feats[0].get("geometry") or {}
        props = feats[0].get("properties") or {}
    else:
        geom = data.get("geometry") or {}
        props = data.get("properties") or {}
    if geom.get("type") != "LineString":
        return [], props
    coords = geom.get("coordinates") or []
    out: list[list[float]] = []
    for c in coords:
        if isinstance(c, (list, tuple)) and len(c) >= 2:
            out.append([float(c[0]), float(c[1])])
    return out, props


def load_famous_maps(extra_dir: str | Path | None = None) -> list[dict[str, Any]]:
    """Return [{id, name, officialLine, origin:{lat,lon}, lengthHint}]."""
    dirs = [_FAMOUS_DIR]
    if extra_dir is not None:
        dirs.insert(0, Path(extra_dir))
    catalog: list[dict[str, Any]] = []
    seen: set[str] = set()
    for map_id, title, path in FAMOUS_MAP_FILES:
        if not path.is_file():
            # try alternate dirs
            found = None
            for d in dirs:
                cand = d / path.name
                if cand.is_file():
                    found = cand
                    break
            path = found  # type: ignore[assignment]
        if path is None or not Path(path).is_file():
            continue
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        line, props = _line_from_geojson(data)
        if len(line) < 2:
            continue
        name = str(props.get("Name") or props.get("name") or title)
        catalog.append(
            {
                "id": map_id,
                "name": name,
                "officialLine": line,
                "origin": {"lat": float(line[0][1]), "lon": float(line[0][0])},
                "lengthHint": props.get("length") or props.get("length_m"),
            }
        )
        seen.add(map_id)
    return catalog


def find_famous_map(map_id: str, catalog: Optional[list[dict]] = None) -> Optional[dict]:
    cat = catalog if catalog is not None else load_famous_maps()
    key = map_id.strip().lower()
    for m in cat:
        if str(m["id"]).lower() == key or str(m["name"]).lower() == key:
            return m
    return None
