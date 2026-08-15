# FSAE 6DOF vehicle type

## Goal

Add a third vehicle type, `fsae-6dof`, so UBCO Motorsports can run G-G diagrams and optimal lap times on their 2026 EV using fastest-lap’s existing Newton–Euler 6DOF chassis. Kart (`kart-6dof`) and F1 (`f1-3dof`) stay unchanged.

## Locked decisions

- New type, not an in-place kart patch.
- Sprung 6DOF only: each corner is `kw + cs + kt` (no unsprung mass). MATLAB 2-DOF quarter-car remains the ride tool.
- G-G first, then optimal lap time.
- Tires: Pacejka block in XML; Hoosier TTC numbers replace the placeholder when provided.
- Rear independent wheel slips + viscous LSD; front and rear brakes; throttle + brake bias; aero at a pressure center; max-power engine (80 kW) with FSAE geometry/aero/mass from the 2026 spec.

## Architecture

```
Tire_pacejka_std × 4 (NORMAL)
  → Axle_car_6dof_fsae front (STEERING_WITH_KAPPA)
  → Axle_car_6dof_fsae rear  (POWERED_WITH_DIFFERENTIAL)
      → Chassis_car_6dof_fsae (heave/roll/pitch + throttle + brake_bias + pressure_center)
          → Road → Dynamic_model_car
```

Public type string: `fsae-6dof`  
C++ vehicle: `fsae6dof` / `fsae6dof_all`  
Database: `database/vehicles/fsae/ubco-2026-ev.xml`

## Corner force

Reuse the kart axle algebraic spring network, with `stiffness/wheel-rate` as `k_chassis` (series with `k_tire`) and `stiffness/antiroll` as L/R coupling. Add `stiffness/damper` `cs` so the contact load is `Fz = kt·w + cs·ṡ` (no extra states). Hub motion still comes from heave/roll/pitch.

## Spin / powertrain

Per-wheel dimensionless kappa (F1 3DOF style). Rear: engine torque split 50/50 minus `differential_stiffness·(ωL−ωR)`. Front and rear brakes with chassis `brake_bias` (1 = all front). No boost, no battery energy limit, no Drexler lock-% curve.

## Controls

Steering, throttle in `[-1, 1]`, brake bias in `[0, 1]`.

## Out of scope

Unsprung mass, wishbone kinematics, ride-height aero maps, ABS, battery limiter, camber/caster as states.

## Tests

Load XML, assert input/control index layout, evaluate the ODE at a straight-running state (finite Fz, no NaNs). Register `fsae-6dof` in `fastestlapc.cpp` so Python `create_vehicle_from_xml` works.
