# FSAE further ideas (fastest-lap, not OpenLAP)

## Goal

Meet the project’s **further ideas** and validation requirement inside fastest-lap’s existing `fsae-6dof` vehicle. Do not port OpenLAP / OpenVEHICLE / OpenTRACK parameter names or the MATLAB app.

Project objectives this stack serves:

- Modular low-to-medium fidelity FSAE EV model
- Each increment has a unit/physics check
- G-G and optimal-laptime remain usable
- Car-like powertrain, aero, tires, and 6DOF chassis outputs

## Out of scope

- OpenLAP `sim.*` / OpenVEHICLE / OpenTRACK I/O
- MATLAB app
- Three-node tire thermal (inner/center/outer)
- 3D suspension hardpoints, roll-center migration, motion-ratio variation
- Battery SOC as a state, inverter maps, ABS
- Track banking / elevation (still rejected)

## Objectives (stacked PRs)

### 1. EV powertrain

Replace “ICE max-power / P=Tω” as the only FSAE motor model with an **electric torque–speed envelope**:

- Peak motor torque (constant) up to base speed
- Peak power (80 kW FSAE cap) above base speed
- Single-speed `gear-ratio` between motor and axle
- Regen: negative throttle applies `regen_coefficient * envelope` as motor braking; friction brakes still apply
- Optimal-laptime integral: `battery-energy` (motor mechanical power)

XML (`vehicle/rear-axle/engine/`): `maximum-power`, `peak-torque`, `gear-ratio`. Rear axle: `regen_coefficient`.

Kart/F1 engines unchanged: envelope mode is opt-in when `peak-torque` is present.

### 2. Low-fidelity aero maps

Keep constant `Cl`/`Cd`/`A`/`rho`. Add linear maps used at force assembly:

- `Cl_eff = Cl * (1 + dCl_dz * z + dCl_dmu * mu)`
- `Cd_eff = Cd * (1 + dCd_dz * z + dCd_dmu * mu)`
- Scales clamped to `(0.2, 3.0)` so the NLP cannot invert aero

Outputs:

- `chassis.aerodynamics.cl_effective`, `cd_effective`
- `chassis.aerodynamics.front_distribution` = `(x_pc - x_rear) / wheelbase`

Pressure center stays the aero balance parameter (already 48% front).

### 3. Single-node tire thermal

One thermal mass per tire (four extra chassis states after heave/roll/pitch):

`C * dT/dt = |dissipation| - h * (T - T_amb)`

Grip scale on tangential Pacejka forces (not Fz):

`mu_scale = 1 - k_mu * ((T - T_opt)/T_opt)^2`, clamped to `[0.5, 1.1]`

Shared XML under `vehicle/chassis/tire-thermal/`: `capacity`, `cooling`, `t-ambient`, `t-optimal`, `grip-sensitivity`.

G-G / steady-state hold T at `t-ambient` (isothermal). Propagation and OLT evolve T.

### 4. Linear kinematic gains (6DOF outputs)

Rigid-body 6DOF already exists. Add **linear kinematic gains**, not hardpoint IK:

- `camber = camber_static + camber_gain_roll * phi` (left/right opposite)
- `toe = toe_static + toe_gain_roll * phi` (plus front steer)

Camber is an extra X rotation on the tire frame; toe adds to the Z rotation.

Outputs: heave, roll, pitch, and per-tire camber/toe.

XML under each axle `kinematics/`: `camber_static`, `camber_gain_roll`, `toe_static`, `toe_gain_roll`.

### 5. Validation suite

Controlled-input checks, not OptimumLap/on-track (data not available):

- EV: torque at low rpm equals `peak_torque * gear_ratio`; high rpm follows `Pmax / omega_wheel`
- Aero: lowering heave (`z` down) increases `cl_effective` when `dCl_dz < 0`
- Thermal: sliding dissipation ⇒ `dT/dt > 0` at `T = T_amb`
- Kinematics: known roll ⇒ expected camber sign/magnitude
- Load transfer: at lateral acceleration, inner/outer `Fz` split has the same sign as `m * ay * h / t`
- G-G smoke: one speed, few points, finite ax/ay if Ipopt is present

## Architecture

No new vehicle type. Extend:

- `Engine` (opt-in envelope)
- `Tire` (`scale_xy_forces`)
- `Axle_car_6dof_fsae` (regen, kinematics, thermal scale)
- `Chassis_car_6dof_fsae` (aero maps, thermal states, outputs)
- `fsae6dof` (integral battery energy; T defaults in steady-state)
- `database/vehicles/fsae/ubco-2026-ev.xml`
- `src/test/vehicles/fsae6dof_test.cpp` and `src/test/actuators/engine_test.cpp`

## Defaults (UBCO 2026 EV)

| Parameter | Value |
|---|---|
| Peak motor torque | 240 N·m |
| Max power | 80 kW |
| Gear ratio | 4.8 |
| Regen coefficient | 0.3 |
| dCl_dz | −8.0 /m |
| dCl_dmu | 2.0 /rad |
| dCd_dz | −2.0 /m |
| dCd_dmu | 0.5 /rad |
| Thermal C | 900 J/K |
| Thermal h | 15 W/K |
| T_amb | 298.15 K |
| T_opt | 353.15 K |
| k_mu | 0.3 |
| Camber static | −1.0 deg |
| Camber gain (roll) | 0.3 rad/rad |
| Toe static / gain | 0 |

## Test plan

Each PR adds failing-then-passing Google tests in `vehicles_test` (and engine tests for PR1). Run from `/workspace/build/src/test/vehicles` with `LD_LIBRARY_PATH` set. Do not commit `examples/python/fastest_lap.py`.
