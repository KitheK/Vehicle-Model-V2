# Setup ranking board Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Ranking tab where the team saves QSS setups, compares them, opens a detail page with car specs plus MATLAB charts, downloads Car `.xlsx`, and ghosts one save on the HUD.

**Architecture:** `qss_ranking.py` owns ranking.json (save, sort, filter, downsample, xlsx export). Studio posts a record after Calculate. Ranking HTML is a board plus `#id` detail. HUD fetches ranking.json for one cyan ghost. Local HTTP API writes `qss_out/ranking.json`; Cloudflare uses `QssStore` key `ranking.json`.

**Tech Stack:** Python 3, openpyxl, unittest, static HTML/JS, Cloudflare Worker Durable Object.

## Global Constraints

- Do not change the C++ `fsae-6dof` ODE.
- Ranking consumes QSS summaries, `list_car_fields` snapshots, and downsampled lap channels only.
- Persist `ranking.json` locally under the Studio out dir; on Cloudflare as `QssStore` `ranking.json`.
- Ghost and MATLAB channels inlined per record; downsample so one record stays under ~200 kB.
- Nav on every page: HUD | MATLAB | Studio | Ranking.
- Car download is a real OpenVEHICLE `.xlsx` via `patch_car_xlsx` on the UBCO template.

---

### Task 1: Ranking core library + tests

**Files:**
- Create: `examples/python/fsae/qss_ranking.py`
- Create: `examples/python/fsae/test_qss_ranking.py`

- [x] Implement load/save/sort/filter/delete, downsample, build_record, export_car_xlsx
- [x] Tests for sort, map filter, delete, downsample, xlsx Kind=car and Total Mass

### Task 2: Ranking board + detail page

**Files:**
- Create: `examples/python/fsae/qss_ranking.html`

- [x] Board table, sort, map filter, detail `#id` with car table + MATLAB canvases, xlsx download

### Task 3: Studio save + load setup; job channels

**Files:**
- Modify: `examples/python/fsae/qss_job.py` (return compact channels)
- Modify: `examples/python/fsae/qss_studio.html`
- Modify: `examples/python/fsae/qss_browser.py` (xlsx helper for Pyodide)

### Task 4: HUD ghost + nav on all pages

**Files:**
- Modify: `qss_hud.html`, `qss_results.html`, `qss_studio.html`

### Task 5: Local API + Worker + build_pages

**Files:**
- Modify: `qss_server.py`, `src/index.js`, `build_pages.py`

### Task 6: Verify tests and template copy
