# Vehicle-Model-V2

Standalone vehicle-dynamics model for the **UBCO 2026 FSAE EV**.

This is **not** a GitHub fork. It is the home for the `fsae-6dof` car: setup
exploration, numerical G-G diagrams, quasi-steady-state (QSS) laps, and the
live HUD. The Newton–Euler engine is derived from
[fastest-lap](https://github.com/juanmanzanero/fastest-lap) (MIT); see
[`NOTICE.md`](NOTICE.md) and [`LICENSE`](LICENSE).

Public type string: **`fsae-6dof`** · C++ type: **`fsae6dof`**

| Need | How this repo meets it |
|---|---|
| G-G envelope vs speed | Python `gg_diagram()` on `fsae-6dof` |
| QSS lap + HUD | `examples/python/fsae/run_qss.py` on an OpenTRACK workbook |
| Optimal lap time (transient NLP) | Python `optimal_laptime()` — registered, not yet a green run |
| FSAE 80 kW / peak-torque motor | EV torque–speed envelope + regen in `ubco-2026-ev.xml` |
| Heave/pitch aero | Linear Cl/Cd maps vs `z` and pitch `μ` |
| Tire temperature | One thermal node per tire; grip scales Pacejka Fx/Fy |
| Camber / toe vs roll | Linear kinematic gains (not hardpoint IK) |
| Physics checks | Google Test suite `fsae6dof*` |

Vehicle workbook (source of numbers): [`database/vehicles/fsae/ubco-2026-ev.xlsx`](database/vehicles/fsae/ubco-2026-ev.xlsx)
Vehicle XML (what the C++/Python API loads): [`database/vehicles/fsae/ubco-2026-ev.xml`](database/vehicles/fsae/ubco-2026-ev.xml)
Design notes: [`docs/superpowers/specs/2026-08-14-fsae-6dof-design.md`](docs/superpowers/specs/2026-08-14-fsae-6dof-design.md), [`docs/superpowers/specs/2026-08-14-fsae-further-ideas-design.md`](docs/superpowers/specs/2026-08-14-fsae-further-ideas-design.md)

**Not in this model:** unsprung quarter-car, 3D wishbone IK, 3-node tire thermal, battery SOC as a state, ABS, track banking.

## Layout

```
database/vehicles/fsae/          UBCO 2026 EV (.xlsx + .xml)
database/tracks/fsae_*/          2019 endurance + skidpad OpenTRACK maps
examples/python/fsae/            QSS lap, HUD, OpenVEHICLE / OpenTRACK I/O
src/core/vehicles/fsae6dof.h     Vehicle type
src/core/chassis/*_fsae.*        Axle + chassis
src/test/vehicles/fsae6dof_test.cpp
src/main/c/                      C API → Python ctypes
```

Kart (`kart-6dof`) and F1 (`f1-3dof`) remain in the engine so the shared
chassis / tire / G-G / Ipopt stack still builds and tests. New model work
belongs under `fsae-6dof` and `examples/python/fsae/`.

## How to run

Assume `$VM` is this repository root. Build with GCC (see [Installation](#installation)).
CMake generates `examples/python/fastest_lap.py` (not committed); it already
knows the path to `libfastestlapc`.

```bash
python3 -m pip install -r $VM/requirements.txt
export LD_LIBRARY_PATH=$VM/build/lib:$VM/build/thirdparty/lib:$LD_LIBRARY_PATH
export PYTHONPATH=$VM/examples/python
```

PowerShell:

```powershell
python -m pip install -r "$env:VM\requirements.txt"
$env:PYTHONPATH = "$env:VM\examples\python"
$env:PATH = "$env:VM\build\lib;$env:VM\build\thirdparty\lib;$env:PATH"
```

### 1. Confirm the vehicle loads (C++ tests)

Run from the vehicles test directory so `./database` resolves:

```bash
cd $VM/build/src/test/vehicles
./vehicles_test --gtest_filter='fsae6dof*'
```

XML load, EV envelope, aero maps, tire heating, camber vs roll, load transfer,
regen / battery-energy integral, and a 2-point G-G smoke at 15 m/s.

### 2. Numerical G-G diagram (Python)

```python
import fastest_lap
from fastest_lap import KMH

vehicle = "ubco"
fastest_lap.create_vehicle_from_xml(
    vehicle, "/path/to/database/vehicles/fsae/ubco-2026-ev.xml"
)
ay, ay_minus, ax_max, ax_min = fastest_lap.gg_diagram(vehicle, 54.0 * KMH, 10)
fastest_lap.plot_gg(ay, ay_minus, ax_max, ax_min)
```

### 3. Vehicle / track workbooks

Vehicle numbers are not hardcoded. Drop an OpenVEHICLE-format `.xlsx` (Info +
Torque Curve; optional **FastestLap** sheet) into `database/vehicles/fsae/` and
convert:

```bash
python3 $VM/examples/python/fsae/xlsx_to_xml.py \
    $VM/database/vehicles/fsae/ubco-2026-ev.xlsx \
    -o $VM/database/vehicles/fsae/ubco-2026-ev.xml
```

OpenTRACK Shape workbooks (`Info` + `Shape` with Straight/Left/Right):

```bash
python3 $VM/examples/python/fsae/xlsx_to_track.py \
    $VM/database/tracks/fsae_2019_endurance/2019_endurance.xlsx \
    -o $VM/database/tracks/fsae_2019_endurance/2019_endurance.xml
```

### 4. QSS lap + HUD

```bash
python3 $VM/examples/python/fsae/run_qss.py \
    --vehicle-xlsx $VM/database/vehicles/fsae/ubco-2026-ev.xlsx \
    --vehicle-xml  $VM/database/vehicles/fsae/ubco-2026-ev.xml \
    --track-xlsx   $VM/database/tracks/fsae_2019_endurance/2019_endurance.xlsx \
    -o $VM/qss_out
```

Outputs: `openlap_results.png`, `hud.html`, `hud_frame.png`, `channels.csv`.
Serve the HUD over HTTP (Three.js import map):

```bash
python3 -m http.server 8765 --bind 0.0.0.0 --directory $VM/qss_out
# open http://127.0.0.1:8765/hud.html
```

`--synthetic` skips `gg_diagram` if `libfastestlapc` is missing. `--v-cap`
caps speed (default 40 m/s). `--cam-height` sets the follow-cam field of view.

Hello-world QSS on UBCO 2026 EV / 2019 endurance: **114.552 s**, speed
16.4 / 65.1 / 138.3 km/h, peak |ay| 1.649 g.

`fsae-6dof` rejects elevation/banking tracks. A full transient
`optimal_laptime()` NLP is registered but not yet green; G-G + QSS is the
working optimal-speed path.

Python unit tests (no C library required for viz / xlsx):

```bash
PYTHONPATH=$VM/examples/python python3 -m unittest fsae.test_openvehicle_xlsx
PYTHONPATH=$VM/examples/python python3 -m unittest fsae.test_opentrack_xlsx
PYTHONPATH=$VM/examples/python python3 -m unittest fsae.test_qss_viz
```

## Suspension (fsae-6dof)

Sprung 6DOF only: no unsprung mass, no 3D wishbone IK. Each corner is
algebraic wheel-rate `kw` in series with tire radial stiffness `kt`, plus
damper `cs` and anti-roll coupling. Contact load is
`Fz = smooth_pos(kt·w + cs·ṡ)`. Hub motion comes from chassis heave / roll /
pitch. Camber and toe are linear in roll. MATLAB 2-DOF quarter-car remains
the ride tool. QSS HUD `Fz` values are algebraic load transfer, not this
spring network.

## Installation

GCC is required. On modern GCC (13+), pass `-include utility` so `std::as_const`
is visible.

```bash
mkdir $VM/build
cd $VM/build
cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_FLAGS="-include utility"
cmake --build . -j$(nproc)
```

CMake downloads lion (Ipopt, CppAD, TinyXML2, …) into `build/thirdparty/`.

CMake options: `-DCMAKE_BUILD_TYPE=Debug/Release`, `-DCMAKE_INSTALL_PREFIX=…`,
`-DCODE_COVERAGE=Yes/No`, `-DBUILD_DOC=Yes/No`.

Optional Docker: `sh ./src/scripts/linux/docker_compile.sh`.

The lighter FSAE check is `./vehicles_test --gtest_filter='fsae6dof*'` from
`build/src/test/vehicles`. `ctest` / `applications_test` is the full engine
suite (including kart/F1 Ipopt cases).

## Engine dependencies

- [Ipopt](https://github.com/coin-or/Ipopt) — NLP for optimal laptime
- [CppAD](https://github.com/coin-or/CppAD) — algorithmic differentiation
- [TinyXML-2](https://github.com/leethomason/tinyxml2) — vehicle/track XML
- [lion-cpp](https://github.com/juanmanzanero/lion-cpp) — frames, AD, optimizer glue

Python (`requirements.txt`): numpy, matplotlib, openpyxl.

## What can be done

- **Numerical G-G diagram:** given a vehicle and a speed, compute the ax–ay
  envelope as an optimization problem.
- **Optimal laptime (engine):** fully transient collocation + Ipopt. Wired for
  `fsae-6dof` but not a green run yet.
- **QSS lap:** OpenLAP-style three-pass speed trace on an OpenTRACK polyline
  using the G-G table — this is the working FSAE lap path today.

Kart and F1 example notebooks under `examples/python/` show the same C API
with different XML.

## References

The 6DOF chassis and tire formulation follow the fastest-lap / Lot–Limebeer
literature. See `docs/` and:

1. Tremlett & Limebeer, *Optimal tyre usage for a formula one car*, VSD 2016.
2. Lot & Dal Bianco, *Lap time optimisation of a racing go-kart*, VSD 2016.
3. Perantoni et al., *Optimal Control for a Formula One Car with Variable Parameters*.
