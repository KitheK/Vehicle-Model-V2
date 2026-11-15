# Track workbook named sites (WGS84 in `.xlsx`)

## Goal

Store queryable geographic placement in the OpenTRACK map `.xlsx` so the HUD can show the course at its **original** site and rigidly reproject it to other **named** sites without relying on sidecar geojson alone.

## Sheets

### `OfficialLine`

| Longitude | Latitude |
|-----------|----------|
| … | … |

Original WGS84 racing line (`[lon, lat]`). First vertex = start/finish.

### `Locations`

| Name | Role | Latitude | Longitude | Bearing_deg |
|------|------|----------|-----------|-------------|
| Michigan MIS | original | 42.0688 | -84.2372 | 0 |
| UBCO Lot H | alternate | 49.942079 | -119.392312 | 0 |
| UBC Main Mall | alternate | 49.26675 | -123.24945 | 0 |

- `Role=original`: reference origin for the stored `OfficialLine` (default HUD site).
- `Role=alternate`: other named origins; HUD transforms the line EN-relative to original → new lat/lon, then applies `Bearing_deg` about the new origin.

### `MapCorners` (optional)

| Corner | Latitude | Longitude |
|--------|----------|-----------|
| tl / tr / bl | … | … |

Original-site corners only (image georef). Relocated views do not warp corners.

## Runtime

1. `load_geo_map(track_dir | xlsx)` prefers `OfficialLine` + `Locations` inside the map workbook; falls back to `official_line.geojson`.
2. Payload includes `officialLine` (active site), `officialLineOriginal`, `locations[]`, `activeLocation`.
3. HUD **Site** `<select>` lists `locations[].name`; on change, reproject and recenter follow-cam.
4. Query API: `list_track_locations(path)`, `project_official_line(line, origin, target)`.

## Out of scope

Studio sheet editor UI; uploading geojson once sheets exist.
