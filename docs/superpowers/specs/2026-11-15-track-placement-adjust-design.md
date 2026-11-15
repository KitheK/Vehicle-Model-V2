# Track placement Adjust + download

## Goal

Correct slight georef errors by rigidly nudging the projected official line on the satellite (ENU translate + bearing). Corrections are session-only until the user downloads a corrected map.

## Decisions

- **Adjust mode** (chip): when on, stage drag moves placement; when off, drag pans the camera.
- Geometry: flat ENU shift of site `lat`/`lon`; Alt+drag changes `bearingDeg`. Scale stays the existing Scale control.
- Persistence: session only + **Download** (no localStorage, no auto-write to source workbook).
- Driving / QSS channels unchanged by placement nudge.

## UX

- **Adjust** chip (off by default). Turning Adjust on disables Follow while nudging.
- Drag → east/north metres → update `activeSiteTarget` → `refreshProjectedCourse()`.
- Alt+drag → bearing degrees.
- **Reset placement** restores the session snapshot taken when Adjust was first used (or when the site was applied).
- Status shows live `lat, lon, bearing`.
- **Download map**: only `map_corrected.xlsx` via `POST /api/export-map` (workbook-backed courses: EV 2026 / 2019). Stamps projected OfficialLine + Location onto that map’s Shape workbook.

## Extension (not v1)

- Terrain-aware / elevation-aware ENU (DEM or map relief) so nudge offsets account for hills and vertical datum differences.
- True 3D elevation channel on OfficialLine.
- Vertex editing of the polyline (non-rigid).

## Out of scope (v1)

- localStorage; auto-write without Download; terrain/elevation math; vertex editing.
