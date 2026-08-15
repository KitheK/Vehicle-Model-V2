"""OpenLAP-style quasi-steady-state lap along an OpenTRACK mesh.

Uses numerical G-G envelopes from fastest-lap (`gg_diagram`) at several
speeds, then does the classic three-pass QSS construction:

1. Corner-limited speed  v_max[i] from |ay| = v^2 |kappa|
2. Forward acceleration limited by ax_max(v, ay)
3. Backward braking limited by ax_min(v, ay)

The racing line is the OpenTRACK Shape polyline (same as MATLAB OpenLAP).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Sequence, Tuple

from fsae.opentrack_xlsx import OpenTrackMesh


@dataclass
class GGTable:
    speeds: List[float]
    ay: List[List[float]]
    ax_max: List[List[float]]
    ax_min: List[List[float]]


@dataclass
class QSSResult:
    s: List[float]
    x: List[float]
    y: List[float]
    kappa: List[float]
    v: List[float]
    ax: List[float]
    ay: List[float]
    time: List[float]
    lap_time: float
    v_max: List[float]


def build_gg_table(vehicle: str, speeds_mps: Sequence[float], n_points: int = 8) -> GGTable:
    import fastest_lap

    ay_all, ax_max_all, ax_min_all = [], [], []
    for speed in speeds_mps:
        ay, _ay_minus, ax_max, ax_min = fastest_lap.gg_diagram(vehicle, float(speed), int(n_points))
        ay_all.append([abs(v) for v in ay])
        ax_max_all.append(list(ax_max))
        ax_min_all.append(list(ax_min))
    return GGTable(speeds=list(map(float, speeds_mps)), ay=ay_all, ax_max=ax_max_all, ax_min=ax_min_all)


def _interp_speed(table: GGTable, speed: float, which: str, ay_abs_g: float) -> float:
    """Linear interpolate ax_max / ax_min [g] at (speed, |ay|)."""
    v = max(table.speeds[0], min(speed, table.speeds[-1]))
    i1 = 0
    for i in range(len(table.speeds) - 1):
        if table.speeds[i] <= v <= table.speeds[i + 1]:
            i1 = i
            break
        i1 = i
    i2 = min(i1 + 1, len(table.speeds) - 1)
    t = 0.0 if table.speeds[i2] == table.speeds[i1] else (v - table.speeds[i1]) / (table.speeds[i2] - table.speeds[i1])

    def ax_at(idx: int) -> float:
        ays = table.ay[idx]
        axs = table.ax_max[idx] if which == "max" else table.ax_min[idx]
        ay = max(0.0, min(ay_abs_g, ays[-1]))
        for j in range(len(ays) - 1):
            if ays[j] <= ay <= ays[j + 1]:
                u = 0.0 if ays[j + 1] == ays[j] else (ay - ays[j]) / (ays[j + 1] - ays[j])
                return axs[j] + u * (axs[j + 1] - axs[j])
        return axs[-1]

    return (1.0 - t) * ax_at(i1) + t * ax_at(i2)


def _ay_peak_g(table: GGTable, speed: float) -> float:
    v = max(table.speeds[0], min(speed, table.speeds[-1]))
    i1 = 0
    for i in range(len(table.speeds) - 1):
        if table.speeds[i] <= v <= table.speeds[i + 1]:
            i1 = i
            break
        i1 = i
    i2 = min(i1 + 1, len(table.speeds) - 1)
    t = 0.0 if table.speeds[i2] == table.speeds[i1] else (v - table.speeds[i1]) / (table.speeds[i2] - table.speeds[i1])
    return (1.0 - t) * table.ay[i1][-1] + t * table.ay[i2][-1]


def _v_corner(kappa: float, table: GGTable, v_cap: float) -> float:
    kabs = abs(kappa)
    if kabs < 1.0e-6:
        return v_cap
    v = min(v_cap, math.sqrt(max(_ay_peak_g(table, 15.0) * 9.81 / kabs, 1.0)))
    for _ in range(8):
        ay_g = (v * v * kabs) / 9.81
        ay_max = _ay_peak_g(table, v)
        if ay_g <= ay_max or v < 1.0:
            break
        v = math.sqrt(max(ay_max * 9.81 / kabs, 0.25))
    return max(1.0, min(v, v_cap))


def qss_lap(mesh: OpenTrackMesh, table: GGTable, v_cap: float = 40.0) -> QSSResult:
    n = len(mesh.s)
    g = 9.81
    v_max = [_v_corner(k, table, v_cap) for k in mesh.kappa]

    def step(v: float, kappa: float, ds: float, which: str) -> float:
        ay_g = abs(v * v * kappa) / g
        ax_g = _interp_speed(table, v, which, ay_g)
        return v * v + 2.0 * ax_g * g * ds

    v_acc = [v_max[0]]
    for i in range(n - 1):
        ds = mesh.s[i + 1] - mesh.s[i]
        v2 = step(v_acc[-1], mesh.kappa[i], ds, "max")
        v_acc.append(min(v_max[i + 1], math.sqrt(max(v2, 1.0))))

    v_brk = [0.0] * n
    v_brk[-1] = v_max[-1]
    for i in range(n - 2, -1, -1):
        ds = mesh.s[i + 1] - mesh.s[i]
        # Integrate backward: v_i^2 = v_{i+1}^2 - 2 ax_min ds, ax_min < 0 so this raises speed when braking
        ay_g = abs(v_brk[i + 1] * v_brk[i + 1] * mesh.kappa[i + 1]) / g
        ax_g = _interp_speed(table, v_brk[i + 1], "min", ay_g)
        v2 = v_brk[i + 1] * v_brk[i + 1] - 2.0 * ax_g * g * ds
        v_brk[i] = min(v_max[i], math.sqrt(max(v2, 1.0)))

    v = [min(a, b, c) for a, b, c in zip(v_max, v_acc, v_brk)]
    ay = [vi * vi * k / g for vi, k in zip(v, mesh.kappa)]
    ax = [0.0] * n
    for i in range(n - 1):
        ds = max(mesh.s[i + 1] - mesh.s[i], 1.0e-9)
        ax[i] = (v[i + 1] * v[i + 1] - v[i] * v[i]) / (2.0 * ds) / g
    ax[-1] = ax[-2]
    time = [0.0]
    for i in range(n - 1):
        ds = mesh.s[i + 1] - mesh.s[i]
        v_mean = max(0.5 * (v[i] + v[i + 1]), 0.5)
        time.append(time[-1] + ds / v_mean)
    return QSSResult(
        s=list(mesh.s),
        x=list(mesh.x),
        y=list(mesh.y),
        kappa=list(mesh.kappa),
        v=v,
        ax=ax,
        ay=ay,
        time=time,
        lap_time=time[-1],
        v_max=v_max,
    )
