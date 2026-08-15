"""Reconstruct OpenLAP-style driver and tire channels from a QSS lap.

Throttle / brake come from where the QSS speed trace sits on the G-G envelope
(same split OpenLAP uses after the three-pass solve). Steering and body slip
are the OpenVEHICLE bicycle-model post-process, not a 6DOF state.

Per-tire load / power / energy are lumped-mass estimates (static weight +
ax/ay transfer). They exist so the HUD can speak the same language as
fastest-lap's MATLAB dashboard; they are not contact-patch states.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fsae.qss_lap import GGTable, QSSResult, _interp_speed

G = 9.81

# OpenVEHICLE Info keys that the bicycle model needs. Used when the xlsx omits them.
_BICYCLE_DEFAULTS = {
    "CF": 800.0,  # N/deg
    "CR": 1000.0,
    "steering_rack_ratio": 5.0,
}


@dataclass
class LapView:
    vehicle_name: str
    track_name: str
    lap_time: float
    s: List[float]
    x: List[float]
    y: List[float]
    yaw: List[float]
    kappa: List[float]
    time: List[float]
    v: List[float]
    ax: List[float]
    ay: List[float]
    v_max: List[float]
    tps: List[float]
    bps: List[float]
    delta: List[float]
    beta: List[float]
    steer: List[float]
    fz_fl: List[float]
    fz_fr: List[float]
    fz_rl: List[float]
    fz_rr: List[float]
    power_fl: List[float]
    power_fr: List[float]
    power_rl: List[float]
    power_rr: List[float]
    energy_fl: List[float]
    energy_fr: List[float]
    energy_rl: List[float]
    energy_rr: List[float]
    env_ay: List[float] = field(default_factory=list)
    env_ax_max: List[float] = field(default_factory=list)
    env_ax_min: List[float] = field(default_factory=list)
    env_speed: float = 0.0
    notes: str = ""


def _as_float(params: Dict[str, Any], *keys: str, default: float) -> float:
    for key in keys:
        if key in params and params[key] is not None:
            return float(params[key])
    return float(default)


def _wheelbase_m(params: Dict[str, Any]) -> float:
    if params.get("wheelbase_m") is not None:
        return float(params["wheelbase_m"])
    return _as_float(params, "wheelbase_mm", default=1620.0) / 1000.0


def _df(params: Dict[str, Any]) -> float:
    if params.get("df") is not None:
        return float(params["df"])
    return _as_float(params, "df_percent", default=51.27) / 100.0


def bicycle_steer(
    v: float,
    kappa: float,
    mass: float,
    wheelbase: float,
    df: float,
    cf: float,
    cr: float,
    rack: float,
) -> tuple[float, float, float]:
    """OpenLAP yaw post-process. Returns (steer_wheel_deg, delta_deg, beta_deg)."""
    kinematic = math.degrees(math.atan(wheelbase * kappa)) if abs(kappa) > 1.0e-12 else 0.0
    if abs(v) < 0.5 or abs(cf) < 1.0e-6 or abs(cr) < 1.0e-6:
        return kinematic * rack, kinematic, 0.0
    a = (1.0 - df) * wheelbase
    b = -df * wheelbase
    c00 = 2.0 * cf
    c01 = 2.0 * (cf + cr)
    c10 = 2.0 * cf * a
    c11 = 2.0 * (cf * a + cr * b)
    det = c00 * c11 - c01 * c10
    if abs(det) < 1.0e-9:
        return kinematic * rack, kinematic, 0.0
    b0 = mass * v * v * kappa
    extra = (c11 * b0) / det
    beta = (-c10 * b0) / det
    delta = extra + kinematic
    return delta * rack, delta, beta


def _load_transfer(
    ax_g: float,
    ay_g: float,
    mass: float,
    df: float,
    wheelbase: float,
    track_f: float,
    track_r: float,
    h_cg: float,
) -> tuple[float, float, float, float]:
    """Static + long/lat transfer, Newtons, positive downward."""
    w = mass * G
    f_axle = df * w
    r_axle = (1.0 - df) * w
    dlong = mass * ax_g * G * h_cg / max(wheelbase, 1.0e-3)
    f_axle = f_axle - dlong
    r_axle = r_axle + dlong
    dlat_f = mass * ay_g * G * h_cg * df / max(track_f, 1.0e-3)
    dlat_r = mass * ay_g * G * h_cg * (1.0 - df) / max(track_r, 1.0e-3)
    fl = 0.5 * f_axle - 0.5 * dlat_f
    fr = 0.5 * f_axle + 0.5 * dlat_f
    rl = 0.5 * r_axle - 0.5 * dlat_r
    rr = 0.5 * r_axle + 0.5 * dlat_r
    floor = 50.0
    return max(fl, floor), max(fr, floor), max(rl, floor), max(rr, floor)


def reconstruct_lap(
    result: QSSResult,
    mesh: Any,
    table: GGTable,
    params: Optional[Dict[str, Any]] = None,
    vehicle_name: str = "vehicle",
    track_name: str = "track",
) -> LapView:
    params = dict(params or {})
    mass = _as_float(params, "mass", default=277.2)
    df = _df(params)
    L = _wheelbase_m(params)
    cf = _as_float(params, "CF", default=_BICYCLE_DEFAULTS["CF"])
    cr = _as_float(params, "CR", default=_BICYCLE_DEFAULTS["CR"])
    rack = _as_float(params, "steering_rack_ratio", default=_BICYCLE_DEFAULTS["steering_rack_ratio"])
    track_f = params.get("front_track_m")
    track_r = params.get("rear_track_m")
    if track_f is None:
        track_f = _as_float(params, "front_track_mm", default=1225.0) / 1000.0
    if track_r is None:
        track_r = _as_float(params, "rear_track_mm", default=1220.0) / 1000.0
    h_cg = params.get("h_cg")
    if h_cg is None:
        h_cg = _as_float(params, "cg_height_mm", default=250.0) / 1000.0

    n = len(result.s)
    tps: List[float] = []
    bps: List[float] = []
    delta: List[float] = []
    beta: List[float] = []
    steer: List[float] = []
    fz = {"fl": [], "fr": [], "rl": [], "rr": []}
    power = {"fl": [], "fr": [], "rl": [], "rr": []}
    energy = {"fl": [0.0], "fr": [0.0], "rl": [0.0], "rr": [0.0]}

    for i in range(n):
        v = result.v[i]
        ax_g = result.ax[i]
        ay_g = result.ay[i]
        ay_abs = abs(ay_g)
        ax_max = max(_interp_speed(table, v, "max", ay_abs), 1.0e-4)
        ax_min = min(_interp_speed(table, v, "min", ay_abs), -1.0e-4)
        if ax_g >= 0.0:
            tps.append(max(0.0, min(1.0, ax_g / ax_max)))
            bps.append(0.0)
        else:
            tps.append(0.0)
            bps.append(max(0.0, min(1.0, ax_g / ax_min)))
        sw, ddeg, bdeg = bicycle_steer(v, result.kappa[i], mass, L, df, cf, cr, rack)
        steer.append(sw)
        delta.append(ddeg)
        beta.append(bdeg)
        fl, fr, rl, rr = _load_transfer(ax_g, ay_g, mass, df, L, float(track_f), float(track_r), float(h_cg))
        fz["fl"].append(fl)
        fz["fr"].append(fr)
        fz["rl"].append(rl)
        fz["rr"].append(rr)
        fsum = fl + fr + rl + rr
        p_total = ax_g * G * mass * v
        for key, load in (("fl", fl), ("fr", fr), ("rl", rl), ("rr", rr)):
            power[key].append(p_total * load / fsum)

    for i in range(n - 1):
        dt = max(result.time[i + 1] - result.time[i], 1.0e-6)
        for key in energy:
            prev = energy[key][-1] if i == 0 else energy[key][i]
            p_mean = 0.5 * (power[key][i] + power[key][i + 1])
            energy[key].append(prev + abs(p_mean) * dt)

    env_speed = table.speeds[min(len(table.speeds) // 2, len(table.speeds) - 1)]
    env_idx = min(range(len(table.speeds)), key=lambda j: abs(table.speeds[j] - env_speed))
    env_ay = list(table.ay[env_idx])
    env_ax_max = list(table.ax_max[env_idx])
    env_ax_min = list(table.ax_min[env_idx])

    return LapView(
        vehicle_name=str(params.get("name") or vehicle_name),
        track_name=track_name,
        lap_time=float(result.lap_time),
        s=list(result.s),
        x=list(mesh.x),
        y=list(mesh.y),
        yaw=list(mesh.yaw),
        kappa=list(result.kappa),
        time=list(result.time),
        v=list(result.v),
        ax=list(result.ax),
        ay=list(result.ay),
        v_max=list(result.v_max),
        tps=tps,
        bps=bps,
        delta=delta,
        beta=beta,
        steer=steer,
        fz_fl=fz["fl"],
        fz_fr=fz["fr"],
        fz_rl=fz["rl"],
        fz_rr=fz["rr"],
        power_fl=power["fl"],
        power_fr=power["fr"],
        power_rl=power["rl"],
        power_rr=power["rr"],
        energy_fl=energy["fl"],
        energy_fr=energy["fr"],
        energy_rl=energy["rl"],
        energy_rr=energy["rr"],
        env_ay=env_ay,
        env_ax_max=env_ax_max,
        env_ax_min=env_ax_min,
        env_speed=float(table.speeds[env_idx]),
        notes=(
            "Throttle/brake from QSS G-G leftover; steer/β from OpenVEHICLE bicycle model; "
            "tire P/E from lumped load transfer (not 6DOF contact patches)."
        ),
    )


def channels_as_rows(view: LapView) -> List[Dict[str, float]]:
    rows = []
    n = len(view.s)
    for i in range(n):
        rows.append(
            {
                "distance": view.s[i],
                "time": view.time[i],
                "x": view.x[i],
                "y": view.y[i],
                "yaw": view.yaw[i],
                "speed": view.v[i],
                "speed_kmh": view.v[i] * 3.6,
                "ax_g": view.ax[i],
                "ay_g": view.ay[i],
                "throttle": view.tps[i],
                "brake": view.bps[i],
                "steer_deg": view.steer[i],
                "delta_deg": view.delta[i],
                "beta_deg": view.beta[i],
                "kappa": view.kappa[i],
                "fz_fl": view.fz_fl[i],
                "fz_fr": view.fz_fr[i],
                "fz_rl": view.fz_rl[i],
                "fz_rr": view.fz_rr[i],
                "power_fl": view.power_fl[i],
                "power_fr": view.power_fr[i],
                "power_rl": view.power_rl[i],
                "power_rr": view.power_rr[i],
                "energy_fl": view.energy_fl[i],
                "energy_fr": view.energy_fr[i],
                "energy_rl": view.energy_rl[i],
                "energy_rr": view.energy_rr[i],
            }
        )
    return rows


def write_csv(view: LapView, path: str) -> None:
    rows = channels_as_rows(view)
    if not rows:
        return
    keys = list(rows[0].keys())
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(",".join(keys) + "\n")
        for row in rows:
            handle.write(",".join(f"{row[k]:.6g}" for k in keys) + "\n")
