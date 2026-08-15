# NOTICE

**Vehicle-Model-V2** is a standalone repository for the UBCO Motorsports
FSAE 6DOF EV vehicle model. It is **not** a GitHub fork of any project.

The C++ simulation engine, C API (`libfastestlapc`), and kart / F1 vehicle
types are derived from [fastest-lap](https://github.com/juanmanzanero/fastest-lap)
(MIT License, Copyright (c) 2021 Juan Manzanero). The original license text
is in `LICENSE`.

FSAE-specific work in this repository includes:

- Vehicle type `fsae-6dof` (`src/core/vehicles/fsae6dof.h`,
  `src/core/chassis/axle_car_6dof_fsae.*`, `src/core/chassis/chassis_car_6dof_fsae.*`)
- UBCO 2026 EV OpenVEHICLE workbook and XML (`database/vehicles/fsae/`)
- OpenTRACK tracks (`database/tracks/fsae_2019_endurance/`, `database/tracks/fsae_skidpad/`)
- Python QSS lap, channel reconstruction, and HUD (`examples/python/fsae/`)
- Validation tests (`src/test/vehicles/fsae6dof_test.cpp`)
- Design notes under `docs/superpowers/`
