# Plan: Named sites in track `.xlsx`

1. Add `OfficialLine` / `Locations` / `MapCorners` read-write + `project_official_line` in `opentrack_xlsx.py`.
2. Prefer workbook geo in `load_geo_map`; payload exposes `locations` + `activeLocation`.
3. HUD **Site** dropdown reprojects the line and recenters.
4. Stamp EV 2026 workbook with MIS (original), UBCO Lot H, UBC Main Mall.
5. Unit tests for project/query + HUD payload strings.
