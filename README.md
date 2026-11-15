# Vehicle-Model-V2

Standalone vehicle-dynamics stack for the **UBCO 2026 FSAE EV** — from OpenVEHICLE / OpenTRACK workbooks through quasi-steady-state (QSS) laps to a geographic HUD on Cloudflare.

The Newton–Euler `fsae-6dof` car is derived from [fastest-lap](https://github.com/juanmanzanero/fastest-lap) (MIT); see [`NOTICE.md`](NOTICE.md) and [`LICENSE`](LICENSE).

**Live Worker:** [vehicle-model-v2.kithekisia.workers.dev](https://vehicle-model-v2.kithekisia.workers.dev/hud.html) · Pages: `hud.html` · `studio.html` · `results.html` · `ranking.html`

Public type string: **`fsae-6dof`** · C++ type: **`fsae6dof`**

## What this project covers

| Area | What you get |
|---|---|
| **Car model** | Sprung 6DOF FSAE EV (`ubco-2026-ev.xlsx` / `.xml`): EV torque–speed envelope, regen, heave/pitch aero maps, tire thermal grip, linear camber/toe vs roll |
| **Track maps** | OpenTRACK Shape workbooks + WGS84 `OfficialLine` / `Locations` (default: FSAE Electric Endurance 2026 at MIS, with UBCO / UBC site projections) |
| **QSS lap** | OpenLAP-style three-pass speed trace from a G-G table — the working FSAE lap path today |
| **Geographic HUD** | Leaflet + Esri satellite, asphalt ribbon + TPS/BPS trail, EV1 GLB car, site search / Adjust placement, map download (`.xlsx`) |
| **Studio** | Upload Car / Map / Driver `.xlsx`, edit defaults, run QSS locally or in the browser (Pyodide on the Worker) |
| **Ranking** | Ghost / compare stored Studio laps |
| **Engine** | Numerical G-G via `gg_diagram()`; transient `optimal_laptime()` registered but not yet a green FSAE run |

**Not in this model:** unsprung quarter-car, 3D wishbone IK, 3-node tire thermal, battery SOC as a state, ABS, track banking / elevation.

## Layout

```
database/vehicles/fsae/                 UBCO 2026 EV (.xlsx + .xml)
database/tracks/fsae_ev_2026_endurance/ Default EV 2026 map + official_line.geojson
database/tracks/famous_maps/            Extra WGS84 courses for the HUD map picker
database/tracks/fsae_2019_endurance/    Legacy 2019 endurance Shape map
examples/python/fsae/                   QSS, HUD template, Studio, OpenVEHICLE / OpenTRACK I/O
public/                                 Cloudflare static assets (HUD, Studio, car.glb, Leaflet)
src/core/vehicles/fsae6dof.h            Vehicle type
src/core/chassis/*_fsae.*               Axle + chassis
src/test/vehicles/fsae6dof_test.cpp
src/main/c/                             C API → Python ctypes
```

Kart (`kart-6dof`) and F1 (`f1-3dof`) remain so the shared chassis / tire / G-G / Ipopt stack still builds. New model work belongs under `fsae-6dof` and `examples/python/fsae/`.

## Quick start (local Studio + HUD)

```powershell
$env:VM = "C:\path\to\Vehicle-Model-V2"
$env:PYTHONPATH = "$env:VM\examples\python"
python -m pip install -r "$env:VM\requirements.txt"
python "$env:VM\examples\python\fsae\qss_server.py" --port 18080 -o "$env:VM\qss_out_ev2026"
# open http://127.0.0.1:18080/studio.html  or  /hud.html
```

Defaults are the UBCO 2026 EV car and **FSAE Electric Endurance 2026** map (OfficialLine + Locations). CLI:

```bash
PYTHONPATH=$VM/examples/python python3 $VM/examples/python/fsae/run_qss.py \
  --track-xlsx $VM/database/tracks/fsae_ev_2026_endurance/fsae_ev_2026_endurance.xlsx \
  --synthetic -o $VM/qss_out_ev2026
```

`--synthetic` skips `gg_diagram` if `libfastestlapc` is missing. `--v-cap` caps speed (default 40 m/s).

## Cloudflare Worker

Git push to `main` builds and deploys a Worker that serves `public/` and keeps the last Studio HUD / MATLAB / ranking payload in a Durable Object.

```bash
python3 -m pip install -r requirements.txt
PYTHONPATH=examples/python python3 examples/python/fsae/build_pages.py
npx wrangler deploy
```

`build_pages.py` writes HUD, MATLAB, Studio, Ranking, `defaults.json`, `qss-runtime.zip` (Pyodide), Leaflet, and the EV1 `car.glb`.

## Workbooks

Three `.xlsx` kinds share a `Format` sheet (`Kind` = `car` | `map` | `driver`):

- **Car** — `Info` + `Torque Curve` + `FastestLap` (OpenVEHICLE + 6DOF fields)
- **Map** — `Info` + `Shape` (`Straight` / `Left` / `Right`); optional `OfficialLine`, `Locations`, `MapCorners` for the geographic HUD
- **Driver** — `Info` + `Channels` + `Envelope`

```bash
python3 $VM/examples/python/fsae/xlsx_convert.py \
  $VM/database/vehicles/fsae/ubco-2026-ev.xlsx
```

## Geographic HUD notes

- **Asphalt** on satellite imagery is the primary track visualization (throttle/brake trail along the WGS84 line).
- **Location** search reprojects the course (ENU) onto named sites or a geocoded place; **Adjust** nudges placement; **Download** exports a corrected map `.xlsx`.
- **Map** picker loads famous courses from `database/tracks/famous_maps/`.
- Preview scale in the header remaps the current lap for display; remesh + QSS needs Studio Calculate with `map_scale`.

## fsae-6dof / G-G / tests

Build with GCC (see [Installation](#installation)). Confirm the vehicle:

```bash
cd $VM/build/src/test/vehicles
./vehicles_test --gtest_filter='fsae6dof*'
```

Numerical G-G (Python):

```python
import fastest_lap
from fastest_lap import KMH
fastest_lap.create_vehicle_from_xml("ubco", "/path/to/ubco-2026-ev.xml")
ay, ay_minus, ax_max, ax_min = fastest_lap.gg_diagram("ubco", 54.0 * KMH, 10)
```

Python unit tests (no C library required for viz / xlsx):

```bash
PYTHONPATH=$VM/examples/python python3 -m unittest fsae.test_qss_viz fsae.test_qss_studio \
  fsae.test_opentrack_xlsx fsae.test_openvehicle_xlsx fsae.test_xlsx_kit
```

## Suspension (fsae-6dof)

Sprung 6DOF only: no unsprung mass, no 3D wishbone IK. Each corner is algebraic wheel-rate `kw` in series with tire radial stiffness `kt`, plus damper `cs` and anti-roll. Contact load is `Fz = smooth_pos(kt·w + cs·ṡ)`. Camber and toe are linear in roll. QSS HUD `Fz` values are algebraic load transfer, not this spring network.

## Installation

GCC is required. On modern GCC (13+), pass `-include utility` so `std::as_const` is visible.

```bash
mkdir $VM/build && cd $VM/build
cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_FLAGS="-include utility"
cmake --build . -j$(nproc)
```

CMake downloads lion (Ipopt, CppAD, TinyXML2, …) into `build/thirdparty/`. Optional Docker: `sh ./src/scripts/linux/docker_compile.sh`.

## Engine dependencies

- [Ipopt](https://github.com/coin-or/Ipopt) — NLP for optimal laptime  
- [CppAD](https://github.com/coin-or/CppAD) — algorithmic differentiation  
- [TinyXML-2](https://github.com/leethomason/tinyxml2) — vehicle/track XML  
- [lion-cpp](https://github.com/juanmanzanero/lion-cpp) — frames, AD, optimizer glue  

Python (`requirements.txt`): numpy, matplotlib, openpyxl.

## Design docs

- [`docs/superpowers/specs/2026-08-14-fsae-6dof-design.md`](docs/superpowers/specs/2026-08-14-fsae-6dof-design.md)  
- [`docs/superpowers/specs/2026-08-14-fsae-further-ideas-design.md`](docs/superpowers/specs/2026-08-14-fsae-further-ideas-design.md)  
- Track placement / geo HUD specs under `docs/superpowers/specs/`

## References

1. Tremlett & Limebeer, *Optimal tyre usage for a formula one car*, VSD 2016.  
2. Lot & Dal Bianco, *Lap time optimisation of a racing go-kart*, VSD 2016.  
3. Perantoni et al., *Optimal Control for a Formula One Car with Variable Parameters*.  
