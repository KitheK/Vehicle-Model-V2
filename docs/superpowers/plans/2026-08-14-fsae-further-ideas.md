# FSAE Further Ideas Implementation Plan

> **For agentic workers:** Execute stacked PRs in order. Each PR is independently testable. Base each branch on the previous. Use TDD: failing test, then implementation.

**Goal:** Add EV envelope, aero maps, single-node tire thermal, linear kinematic gains, and validation tests to `fsae-6dof`.

**Architecture:** Opt-in Engine envelope; FSAE chassis/axle extensions; no new vehicle type; kart/F1 XML unchanged.

**Tech Stack:** C++17, Google Test, fastest-lap XML, CppAD Timeseries_t

## Global Constraints

- Branch names: `Agent/<descriptive-name>-b8e7`
- Stack onto `Agent/fsae-6dof-vehicle-b8e7` then each successor
- Do not change kart/F1 behavior unless Engine envelope is opt-in
- Do not commit `examples/python/fastest_lap.py`
- GCC build with `-include utility`; tests from their own `build/src/test/<suite>` dir
- `LD_LIBRARY_PATH=/workspace/build/lib:/workspace/build/thirdparty/lib`

## Files

- Modify: `src/core/actuators/engine.h`, `engine.hpp`
- Modify: `src/core/tire/tire.h`
- Modify: `src/core/chassis/axle_car_6dof_fsae.h`, `.hpp`
- Modify: `src/core/chassis/chassis_car_6dof.h`, `chassis_car_6dof_fsae.h`, `.hpp`
- Modify: `src/core/vehicles/fsae6dof.h`
- Modify: `database/vehicles/fsae/ubco-2026-ev.xml`
- Modify: `src/test/actuators/engine_test.cpp`, `src/test/vehicles/fsae6dof_test.cpp`

### Task 1: EV powertrain (branch `Agent/fsae-ev-powertrain-b8e7`)

Engine opt-in envelope when `peak-torque` is present. FSAE regen on rear axle. Battery-energy integral.

### Task 2: Aero maps (branch `Agent/fsae-aero-maps-b8e7`)

Linear Cl/Cd vs heave/pitch; front distribution output.

### Task 3: Tire thermal (branch `Agent/fsae-tire-thermal-b8e7`)

Four temperature states; `Tire::scale_xy_forces`; grip scale.

### Task 4: Kinematic gains (branch `Agent/fsae-kinematic-gains-b8e7`)

Camber/toe from roll + steer; 6DOF outputs.

### Task 5: Validation suite (branch `Agent/fsae-validation-suite-b8e7`)

Load-transfer sign check; G-G smoke if Ipopt present.
