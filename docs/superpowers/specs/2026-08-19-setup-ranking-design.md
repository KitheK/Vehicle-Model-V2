# Setup ranking board and two-car HUD ghost

## Goal

Let UBCO Motorsports compare car **builds** (mass, power, aero, suspension numbers, etc.) so they can pick a configuration to pursue. After each QSS Calculate they can **save** that setup. A ranking board lists saved runs. The HUD can overlay **one ghost** (a saved run) next to the current lap.

## Locked decisions

- Board **and** two-car HUD (current + one ghost). Not dual Studio editors in v1.
- Sort is **user-picked column** (lap time, speeds, peak ay, mass, max power, saved time). Default sort: lap time ascending (fastest first).
- One board with a **map filter** that defaults to the map of the latest run. Turning the filter off shows every map. Ghosting a different map is allowed; the HUD shows a warning.
- Save is **explicit** (name + Save to ranking), not automatic on every Calculate.
- Persist locally as `qss_out/ranking.json`. On Cloudflare, persist in the existing `QssStore` Durable Object under keys `ranking.json` and `ghost/<id>.json`.
- Do not change the C++ `fsae-6dof` ODE. Ranking consumes QSS summaries and car field snapshots only.
- Out of v1: four-car overlay, energy/SOC rank, deleting Cloudflare Containers, live two-editor Studio.

## Ranking record

Each saved entry is JSON:

```
{
  "id": "<uuid>",
  "name": "290 kg / 80 kW",
  "saved_at": "<ISO-8601>",
  "map": "2019 Endurance",
  "vehicle": "UBCO 2026 EV",
  "lap_time": 117.26,
  "speed_kmh": { "min": 16.4, "mean": 65.1, "max": 138.3 },
  "peak_ay_g": 1.65,
  "v_cap": 40.0,
  "synthetic": true,
  "car": { "mass": 290, "maximum_power": 80000, "fields": [ /* list_car_fields snapshot */ ] },
  "ghost": { "s": [], "x": [], "y": [], "v": [], "time": [] }
}
```

`car.fields` is the Studio editor snapshot (same objects as `list_car_fields`). The board’s mass/power columns read well-known descriptions (`Total Mass`, `Maximum Power`) from that list; missing keys show as `—`.

`ghost` channels are downsampled if needed so one record stays under ~200 kB. HUD interpolates in time like the live payload.

## UI

**Studio** (`qss_studio.html`)

- After a successful Calculate: name input (default `vehicle · map · lap_time`) and **Save to ranking**.
- Nav link: Ranking.
- Status line confirms save or duplicate-name overwrite (overwrite only if the user confirms).

**Ranking** (`qss_ranking.html`, served as `ranking.html`)

- Table: name, map, lap time, min/mean/max km/h, peak ay, mass, max power, saved at.
- Click column headers to sort; indicator on the active column.
- Map filter: dropdown, default = latest run’s map; option “All maps”.
- Actions per row: **Ghost on HUD**, **Load setup** (writes car fields back into Studio), **Delete**.
- Empty state: “No saved setups. Calculate in Studio, then Save to ranking.”

**HUD** (`qss_hud.html`)

- Control: Ghost select (`None` + saved names for which ghost channels exist).
- Current car/trail unchanged. Ghost is a second trail and a second car stamp in a distinct color (cyan vs live orange/green).
- If ghost map ≠ current payload map, show a small warning, still draw.
- Mini-map: ghost position as a second marker.

MATLAB results page is unchanged except a Ranking nav link.

## Data flow

```
Studio Calculate
  → QSS job (existing)
  → HUD/MATLAB artifacts (existing)
  → optional Save
       → append ranking.json
       → store ghost channels from that run

Ranking page
  → GET ranking.json
  → sort/filter in the browser

HUD
  → GET ranking.json for the ghost list
  → GET ghost/<id>.json if not inlined
  → draw live D plus ghost G
```

**Local server** (`qss_server.py`): `GET/PUT /api/ranking`, `DELETE /api/ranking/<id>`, `GET /ranking.html`. File: `{out_dir}/ranking.json`.

**Cloudflare Worker**: same paths on `QssStore`. Studio already PUTs `hud.html` / `results.html`; Save also PUTs ranking JSON. HUD ghost fetch uses `/api/artifact/ranking.json`.

**Browser QSS (Pyodide)**: after `run_studio`, Save uses the in-memory summary + `view` channels already used to write HUD payload (extract `s,x,y,v,time` from the Python result or from the generated payload). Extend `run_studio` to return those arrays in the summary so Save does not re-parse HUD HTML.

## Error handling

- Save with empty name: reject.
- Ranking file missing: treat as `[]`.
- Corrupt JSON: show error, do not wipe the file.
- Ghost id missing channels: skip overlay, status “no ghost path for this save”.
- Cloudflare DO write failure: surface in Studio status; do not claim saved.

## Tests

- `test_qss_ranking.py`: create two fake summaries, save, sort by lap time and by mass, filter by map, delete, downsample ghost length.
- HUD template contains ghost select and a second trail draw path (`G.` or `ghost`).
- Studio template contains Save to ranking and ranking.html nav.
- Existing QSS / Studio tests still pass.

## Files (implementation, not this spec)

- New: `examples/python/fsae/qss_ranking.py`, `qss_ranking.html`, `test_qss_ranking.py`
- Edit: `qss_studio.html`, `qss_hud.html`, `qss_results.html`, `qss_server.py`, `qss_browser.py`, `src/index.js`, `build_pages.py`, nav on all three pages
