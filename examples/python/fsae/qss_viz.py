"""OpenLAP result plots and a fastest-lap-style 6DOF dashboard for a QSS lap.

Result figures put each channel in its own axes, grouped (speed, curvature,
acceleration, driver inputs, attitude). The HTML HUD keeps the original dark
grid (header, follow-cam stage, side DRIVER/G-G/TIRES/MAP, bottom telemetry)
with the asphalt ribbon follow-cam and a UBCO-liveried 3D car on track and in
the tires card. Each tire cell updates Fz / P / E every frame.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional

from fsae.qss_channels import LapView

ORANGE = "#d95319"
CYAN = "#00ffff"
MAGENTA = "#ff00ff"
GREEN = "#00a65a"
RED = "#e53935"
BLUE = "#1f77b4"
NAVY = "#0b1f4a"

_HERE = Path(__file__).resolve().parent
_HUD_TEMPLATE = _HERE / "qss_hud.html"
_RESULTS_TEMPLATE = _HERE / "qss_results.html"


def _setup_mpl():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#333",
            "axes.labelcolor": "#111",
            "xtick.color": "#111",
            "ytick.color": "#111",
            "text.color": "#111",
            "font.size": 9,
            "axes.grid": True,
            "grid.alpha": 0.28,
            "grid.linestyle": "--",
        }
    )
    return plt


def _style(ax, ylabel: str, xlabel: str | None = None, title: str | None = None) -> None:
    ax.set_ylabel(ylabel)
    if xlabel:
        ax.set_xlabel(xlabel)
    if title:
        ax.set_title(title, loc="left", fontsize=10, fontweight="bold", pad=4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.margins(x=0.01)


def plot_openlap_results(view: LapView, path: str | Path) -> Path:
    """Grouped OpenLAP results: one axes per channel, plus GGV and track map."""
    plt = _setup_mpl()
    from matplotlib.collections import LineCollection
    import numpy as np

    s = np.array(view.s)
    v_kmh = np.array(view.v) * 3.6
    gsum = np.hypot(view.ax, view.ay)
    fig = plt.figure(figsize=(13.2, 24.0), dpi=130)
    fig.suptitle(
        f"{view.vehicle_name}  ·  {view.track_name}\n"
        f"QSS lap {view.lap_time:.3f} s    min/mean/max  "
        f"{min(v_kmh):.1f} / {v_kmh.mean():.1f} / {max(v_kmh):.1f} km/h",
        fontsize=14,
        fontweight="bold",
        y=0.995,
    )
    outer = fig.add_gridspec(
        6,
        1,
        height_ratios=[1.15, 1.05, 3.15, 2.15, 3.15, 2.45],
        hspace=0.38,
        left=0.08,
        right=0.97,
        top=0.96,
        bottom=0.03,
    )

    ax = fig.add_subplot(outer[0])
    ax.plot(s, v_kmh, color=ORANGE, lw=1.8, label="Speed")
    ax.plot(s, np.array(view.v_max) * 3.6, color="#888", lw=0.9, ls="--", label="Corner limit")
    _style(ax, "Speed [km/h]", title="Speed")
    ax.legend(loc="upper right", frameon=False)

    ax = fig.add_subplot(outer[1], sharex=ax)
    ax.plot(s, view.kappa, color=BLUE, lw=1.4)
    _style(ax, "κ [1/m]", title="Curvature")

    acc = outer[2].subgridspec(3, 1, hspace=0.18)
    ax_lon = fig.add_subplot(acc[0], sharex=ax)
    ax_lat = fig.add_subplot(acc[1], sharex=ax)
    ax_sum = fig.add_subplot(acc[2], sharex=ax)
    ax_lon.plot(s, view.ax, color=GREEN, lw=1.4)
    ax_lat.plot(s, view.ay, color=BLUE, lw=1.4)
    ax_sum.plot(s, gsum, color="#111", lw=1.4)
    ax_lon.axhline(0, color="#ccc", lw=0.6)
    ax_lat.axhline(0, color="#ccc", lw=0.6)
    _style(ax_lon, "LonAcc [g]", title="Acceleration")
    _style(ax_lat, "LatAcc [g]")
    _style(ax_sum, "GSum [g]")

    inp = outer[3].subgridspec(2, 1, hspace=0.18)
    ax_tps = fig.add_subplot(inp[0], sharex=ax)
    ax_bps = fig.add_subplot(inp[1], sharex=ax)
    ax_tps.plot(s, [t * 100 for t in view.tps], color=GREEN, lw=1.4)
    ax_bps.plot(s, [b * 100 for b in view.bps], color=RED, lw=1.4)
    ax_tps.set_ylim(-5, 110)
    ax_bps.set_ylim(-5, 110)
    _style(ax_tps, "tps [%]", title="Driver inputs")
    _style(ax_bps, "bps [%]")

    ang = outer[4].subgridspec(3, 1, hspace=0.18)
    ax_sw = fig.add_subplot(ang[0], sharex=ax)
    ax_de = fig.add_subplot(ang[1], sharex=ax)
    ax_be = fig.add_subplot(ang[2], sharex=ax)
    ax_sw.plot(s, view.steer, color=ORANGE, lw=1.3)
    ax_de.plot(s, view.delta, color=BLUE, lw=1.3)
    ax_be.plot(s, view.beta, color="#7e57c2", lw=1.3)
    _style(ax_sw, "Steer wheel [deg]", title="Attitude")
    _style(ax_de, r"δ [deg]")
    _style(ax_be, r"β [deg]", xlabel="Distance [m]")

    bottom = outer[5].subgridspec(1, 2, wspace=0.22)
    axg = fig.add_subplot(bottom[0, 0])
    if view.env_ay:
        ay_p = list(view.env_ay)
        ay_m = [-a for a in ay_p]
        axg.plot(ay_p, view.env_ax_max, color=ORANGE, lw=1.2)
        axg.plot(ay_p, view.env_ax_min, color=ORANGE, lw=1.2)
        axg.plot(ay_m, view.env_ax_max, color=ORANGE, lw=1.2)
        axg.plot(ay_m, view.env_ax_min, color=ORANGE, lw=1.2, label="GGV envelope")
    sc = axg.scatter(view.ay, view.ax, c=v_kmh, s=10, cmap="plasma", zorder=3)
    fig.colorbar(sc, ax=axg, label="Speed [km/h]", fraction=0.046)
    axg.set_xlabel("LatAcc [g]")
    axg.set_ylabel("LonAcc [g]")
    axg.set_aspect("equal", adjustable="box")
    axg.set_title("GGV usage", loc="left", fontsize=10, fontweight="bold")
    axg.legend(loc="lower left", fontsize=8, frameon=False)

    axm = fig.add_subplot(bottom[0, 1])
    pts = np.column_stack([view.x, view.y])
    segs = np.concatenate([pts[:-1, None, :], pts[1:, None, :]], axis=1)
    lc = LineCollection(segs, cmap="plasma", linewidths=2.6)
    lc.set_array(v_kmh[:-1])
    axm.add_collection(lc)
    axm.plot(view.x[0], view.y[0], marker=(3, 0, math.degrees(view.yaw[0]) - 90), color="k", ms=12)
    axm.set_aspect("equal")
    axm.autoscale()
    axm.set_xlabel("X [m]")
    axm.set_ylabel("Y [m]")
    axm.set_title("Track map", loc="left", fontsize=10, fontweight="bold")
    fig.colorbar(lc, ax=axm, label="Speed [km/h]", fraction=0.046)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def _heading(view: LapView, i: int) -> float:
    if i >= len(view.x) - 1:
        i = max(0, len(view.x) - 2)
    dx = view.x[i + 1] - view.x[i]
    dy = view.y[i + 1] - view.y[i]
    if math.hypot(dx, dy) < 1.0e-9:
        return view.yaw[i]
    return math.atan2(dy, dx)


def _bounds(view: LapView, half: float = 3.5):
    xl, yl, xr, yr = [], [], [], []
    n = len(view.x)
    for i in range(n):
        yaw = _heading(view, min(i, n - 2))
        nx, ny = -math.sin(yaw), math.cos(yaw)
        xl.append(view.x[i] + half * nx)
        yl.append(view.y[i] + half * ny)
        xr.append(view.x[i] - half * nx)
        yr.append(view.y[i] - half * ny)
    return xl, yl, xr, yr


def _draw_ubco_car(ax, x: float, y: float, yaw: float, delta: float = 0.0, scale: float = 1.0) -> None:
    """Top-down UBCO FSAE (nose along heading). Matplotlib y-up."""
    from matplotlib.patches import FancyBboxPatch, Rectangle, Circle, Polygon
    import matplotlib.pyplot as plt  # noqa: F401

    c, s = math.cos(yaw), math.sin(yaw)

    def wpt(lx, ly):
        lx = lx - 0.26  # mid-wheelbase on the racing line
        return x + scale * (lx * c - ly * s), y + scale * (lx * s + ly * c)

    def poly(pts, **kw):
        ax.add_patch(Polygon([wpt(px, py) for px, py in pts], closed=True, **kw))

    track = 1.22
    wb = 1.62
    tires = [(-0.55, -track / 2, 0.0), (-0.55, track / 2, 0.0), (wb - 0.55, -track / 2, delta), (wb - 0.55, track / 2, delta)]
    for tx, ty, st in tires:
        tx = tx - 0.26
        cs, ss = math.cos(yaw + st), math.sin(yaw + st)
        corners = []
        for dx, dy in ((-0.28, -0.11), (0.28, -0.11), (0.28, 0.11), (-0.28, 0.11)):
            corners.append((x + scale * ((tx + dx) * cs - (ty + dy) * ss), y + scale * ((tx + dx) * ss + (ty + dy) * cs)))
        ax.add_patch(Polygon(corners, closed=True, facecolor="#111", edgecolor="none", zorder=6))
    poly([(-0.85, -0.62), (1.55, -0.55), (1.55, 0.55), (-0.85, 0.62)], facecolor="#1a1a1a", zorder=5)
    poly([(-0.15, -0.48), (1.05, -0.50), (1.20, -0.28), (0.15, -0.22)], facecolor=NAVY, zorder=5)
    poly([(-0.15, 0.48), (1.05, 0.50), (1.20, 0.28), (0.15, 0.22)], facecolor=NAVY, zorder=5)
    poly([(1.10, -0.22), (2.35, -0.09), (2.55, 0.0), (2.35, 0.09), (1.10, 0.22)], facecolor="#f4f4f4", zorder=5)
    poly([(-1.05, -0.55), (-0.87, -0.55), (-0.87, 0.55), (-1.05, 0.55)], facecolor=NAVY, zorder=5)
    poly([(2.28, -0.62), (2.42, -0.62), (2.42, 0.62), (2.28, 0.62)], facecolor=NAVY, zorder=5)
    nx, ny = wpt(1.85, 0.0)
    ax.text(nx, ny, "1", color=NAVY, ha="center", va="center", fontsize=7 * scale, fontweight="bold", zorder=7)


def plot_hud_frame(view: LapView, path: str | Path, index: Optional[int] = None, cam_height: float = 80.0) -> Path:
    """Static frame of the dark HUD: asphalt follow-cam plus side cards."""
    plt = _setup_mpl()
    from matplotlib.patches import Polygon, Circle, Rectangle, FancyBboxPatch
    from matplotlib.collections import LineCollection
    import numpy as np

    n = len(view.s)
    i = n // 3 if index is None else max(0, min(index, n - 1))
    bg, panel, line, fg, muted = "#0d1117", "#161b22", "#30363d", "#c9d1d9", "#8b949e"
    fig = plt.figure(figsize=(16, 9), dpi=130, facecolor=bg)

    fig.add_artist(
        FancyBboxPatch((0.008, 0.925), 0.984, 0.062, boxstyle="round,pad=0.004,rounding_size=0.008",
                       facecolor=panel, edgecolor=line, transform=fig.transFigure, linewidth=1)
    )
    fig.text(0.02, 0.958, f"{view.vehicle_name}  ·  {view.track_name}", color=fg, fontsize=13, fontweight="bold")
    fig.text(
        0.02, 0.932,
        f"t = {view.time[i]:.2f} s    {view.v[i]*3.6:.1f} km/h    ax {view.ax[i]:.2f} g    ay {view.ay[i]:.2f} g",
        color=muted, fontsize=10,
    )
    fig.text(0.88, 0.942, f"{view.lap_time:.3f} s", color=ORANGE, fontsize=16, fontweight="bold")

    ax = fig.add_axes([0.01, 0.195, 0.685, 0.715], facecolor="#d5d8dc")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color(line)

    cx, cy = view.x[i], view.y[i]
    yaw = _heading(view, i)
    xl, yl, xr, yr = _bounds(view, 3.5)
    asphalt = list(zip(xl, yl)) + list(zip(reversed(xr), reversed(yr)))
    ax.add_patch(Polygon(asphalt, closed=True, facecolor="#0d1117", edgecolor="none", zorder=1))
    ax.plot(view.x, view.y, color="white", lw=0.8, ls=(0, (4, 4)), zorder=2)

    i0 = max(0, i - 220)
    cols = []
    for k in range(i0, i):
        tps, bps = view.tps[k], view.bps[k]
        if tps >= bps:
            cols.append((0.0, 0.55 + 0.45 * tps, 0.16, 1.0))
        else:
            cols.append((0.65 + 0.35 * bps, 0.08, 0.08, 1.0))
    if i > i0:
        pts = np.column_stack([view.x[i0 : i + 1], view.y[i0 : i + 1]])
        segs = np.concatenate([pts[:-1, None, :], pts[1:, None, :]], axis=1)
        ax.add_collection(LineCollection(segs, colors=cols, linewidths=3.2, zorder=3))

    _draw_ubco_car(ax, cx, cy, yaw, math.radians(view.delta[i]), scale=1.0)
    aspect = 0.685 / 0.715 * 16 / 9
    ax.set_aspect("equal")
    ax.set_xlim(cx - 0.5 * cam_height * aspect, cx + 0.5 * cam_height * aspect)
    ax.set_ylim(cy - 0.5 * cam_height, cy + 0.5 * cam_height)
    ax.set_autoscale_on(False)

    def _card(rect, title):
        a = fig.add_axes(rect, facecolor="#010409")
        for spine in a.spines.values():
            spine.set_color(line)
        a.set_title(title, fontsize=8, loc="left", color=muted, pad=4)
        return a

    axb = _card([0.705, 0.755, 0.28, 0.155], "DRIVER")
    axb.set_xlim(0, 3.2)
    axb.set_ylim(-0.25, 1.15)
    axb.set_xticks([])
    axb.set_yticks([])
    axb.add_patch(Rectangle((0.25, 0), 0.4, view.bps[i], color=RED, zorder=2))
    axb.add_patch(Rectangle((0.80, 0), 0.4, view.tps[i], color=GREEN, zorder=2))
    axb.add_patch(Rectangle((0.25, 0), 0.4, 1.0, fill=False, edgecolor=fg, lw=1.2))
    axb.add_patch(Rectangle((0.80, 0), 0.4, 1.0, fill=False, edgecolor=fg, lw=1.2))
    axb.text(0.45, -0.18, "BPS", ha="center", color=RED, fontsize=8)
    axb.text(1.00, -0.18, "TPS", ha="center", color=GREEN, fontsize=8)
    axb.add_patch(Circle((2.35, 0.50), 0.38, fill=False, edgecolor=fg, lw=1.4))
    ang = math.radians(view.steer[i])
    axb.plot([2.35, 2.35 + 0.38 * math.sin(ang)], [0.50, 0.50 + 0.38 * math.cos(ang)], color=ORANGE, lw=2)

    axg = _card([0.705, 0.575, 0.28, 0.165], "G-G")
    if view.env_ay:
        ay_p = view.env_ay
        ay_m = [-a for a in ay_p]
        axg.plot(ay_p, view.env_ax_max, color=ORANGE, lw=1)
        axg.plot(ay_p, view.env_ax_min, color=ORANGE, lw=1)
        axg.plot(ay_m, view.env_ax_max, color=ORANGE, lw=1)
        axg.plot(ay_m, view.env_ax_min, color=ORANGE, lw=1)
    axg.plot(view.ay[max(0, i - 40) : i + 1], view.ax[max(0, i - 40) : i + 1], color=CYAN, lw=1.2)
    axg.plot(view.ay[i], view.ax[i], "o", color=ORANGE, ms=7)
    axg.set_aspect("equal")
    axg.tick_params(labelsize=6, colors=muted)
    axg.set_facecolor("#010409")
    for spine in axg.spines.values():
        spine.set_color(line)

    axt = _card([0.705, 0.335, 0.28, 0.225], "TIRES")
    axt.set_xlim(-1.6, 3.4)
    axt.set_ylim(-1.45, 1.45)
    axt.set_aspect("equal")
    axt.set_xticks([])
    axt.set_yticks([])
    _draw_ubco_car(axt, 0.15, 0.0, math.pi / 2, math.radians(view.delta[i]), scale=0.42)
    corners = (
        ("FL", view.fz_fl[i], view.power_fl[i], view.energy_fl[i], -1.45, 0.55),
        ("FR", view.fz_fr[i], view.power_fr[i], view.energy_fr[i], 1.55, 0.55),
        ("RL", view.fz_rl[i], view.power_rl[i], view.energy_rl[i], -1.45, -1.15),
        ("RR", view.fz_rr[i], view.power_rr[i], view.energy_rr[i], 1.55, -1.15),
    )
    fz_max = max(max(view.fz_fl), max(view.fz_fr), max(view.fz_rl), max(view.fz_rr), 1.0)
    for name, fz, pwr, energy, x0, y0 in corners:
        u = fz / fz_max
        axt.add_patch(Rectangle((x0, y0), 1.55 * u, 0.16, color=ORANGE if u > 0.75 else GREEN, zorder=4))
        axt.add_patch(Rectangle((x0, y0), 1.55, 0.16, fill=False, edgecolor=line, zorder=5))
        axt.text(
            x0,
            y0 + 0.42,
            f"{name}  Fz {fz:.0f} N\nP {pwr/1000:.2f} kW   E {energy/1e3:.1f} kJ",
            fontsize=6.2,
            color=fg,
            va="bottom",
        )

    axm = _card([0.705, 0.195, 0.28, 0.125], "MAP")
    axm.plot(view.x, view.y, color="#30363d", lw=5)
    axm.plot(view.x, view.y, color="#58a6ff", lw=1.4)
    axm.plot(cx, cy, marker=(3, 0, math.degrees(yaw) - 90), color=ORANGE, ms=9)
    axm.set_aspect("equal")
    axm.set_xticks([])
    axm.set_yticks([])

    axtel = fig.add_axes([0.01, 0.02, 0.98, 0.155], facecolor="#010409")
    for spine in axtel.spines.values():
        spine.set_color(line)
    t0 = view.time[i] - 8.0
    j0 = next((j for j, t in enumerate(view.time) if t >= t0), 0)
    tt = view.time[j0 : i + 1]
    if len(tt) > 1:
        def norm(seq):
            arr = seq[j0 : i + 1]
            lo, hi = min(arr), max(arr)
            if hi - lo < 1e-9:
                return [0.5] * len(arr)
            return [(x - lo) / (hi - lo) for x in arr]

        axtel.plot(tt, norm(view.v), color=MAGENTA, lw=1.5, label="speed")
        axtel.plot(tt, view.tps[j0 : i + 1], color=GREEN, lw=1.2, label="tps")
        axtel.plot(tt, view.bps[j0 : i + 1], color=RED, lw=1.2, label="bps")
        axtel.plot(tt, norm(view.steer), color=CYAN, lw=1.2, label="steer")
    axtel.tick_params(colors=muted, labelsize=7)
    axtel.set_title("Telemetry", fontsize=8, loc="left", color=muted)
    axtel.legend(loc="upper left", fontsize=7, facecolor=panel, edgecolor=line, labelcolor=fg, ncol=4)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def _round_list(values, ndigits: int = 5):
    return [round(float(v), ndigits) for v in values]


def _payload(view: LapView, cam_height: float = 80.0, half_width: float = 3.5) -> dict:
    xl, yl, xr, yr = _bounds(view, half_width)
    return {
        "vehicle": view.vehicle_name,
        "track": view.track_name,
        "lapTime": round(view.lap_time, 4),
        "notes": view.notes,
        "camHeight": cam_height,
        "halfWidth": half_width,
        "s": _round_list(view.s, 4),
        "x": _round_list(view.x, 4),
        "y": _round_list(view.y, 4),
        "yaw": _round_list(view.yaw, 5),
        "kappa": _round_list(view.kappa, 6),
        "vmax": _round_list(view.v_max, 4),
        "xl": _round_list(xl, 4),
        "yl": _round_list(yl, 4),
        "xr": _round_list(xr, 4),
        "yr": _round_list(yr, 4),
        "time": _round_list(view.time, 4),
        "v": _round_list(view.v, 4),
        "ax": _round_list(view.ax, 4),
        "ay": _round_list(view.ay, 4),
        "tps": _round_list(view.tps, 4),
        "bps": _round_list(view.bps, 4),
        "steer": _round_list(view.steer, 3),
        "delta": _round_list(view.delta, 3),
        "beta": _round_list(view.beta, 3),
        "fz": {
            "fl": _round_list(view.fz_fl, 1),
            "fr": _round_list(view.fz_fr, 1),
            "rl": _round_list(view.fz_rl, 1),
            "rr": _round_list(view.fz_rr, 1),
        },
        "power": {
            "fl": _round_list(view.power_fl, 1),
            "fr": _round_list(view.power_fr, 1),
            "rl": _round_list(view.power_rl, 1),
            "rr": _round_list(view.power_rr, 1),
        },
        "energy": {
            "fl": _round_list(view.energy_fl, 1),
            "fr": _round_list(view.energy_fr, 1),
            "rl": _round_list(view.energy_rl, 1),
            "rr": _round_list(view.energy_rr, 1),
        },
        "envAy": _round_list(view.env_ay, 4),
        "envAxMax": _round_list(view.env_ax_max, 4),
        "envAxMin": _round_list(view.env_ax_min, 4),
        "envSpeed": round(view.env_speed, 3),
    }


def _write_html(template: Path, payload: dict, path: str | Path) -> Path:
    html = template.read_text(encoding="utf-8").replace(
        "__PAYLOAD__", json.dumps(payload, separators=(",", ":"))
    )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path


def write_hud_html(view: LapView, path: str | Path, cam_height: float = 80.0, half_width: float = 3.5) -> Path:
    """Self-contained dark HUD with world-aligned asphalt follow-cam and UBCO 3D car."""
    return _write_html(_HUD_TEMPLATE, _payload(view, cam_height, half_width), path)


def write_results_html(view: LapView, path: str | Path, cam_height: float = 80.0, half_width: float = 3.5) -> Path:
    """OpenLAP MATLAB-style page: stacked channels, GGV scatter, track map."""
    return _write_html(_RESULTS_TEMPLATE, _payload(view, cam_height, half_width), path)


def write_summary(view: LapView, path: str | Path) -> Path:
    v_kmh = [x * 3.6 for x in view.v]
    text = (
        f"{view.vehicle_name} on {view.track_name}\n"
        f"QSS lap time: {view.lap_time:.3f} s\n"
        f"Speed: min {min(v_kmh):.1f}  mean {sum(v_kmh)/len(v_kmh):.1f}  max {max(v_kmh):.1f} km/h\n"
        f"Peak |ay|: {max(abs(a) for a in view.ay):.3f} g\n"
        f"Long. accel: {max(view.ax):.3f} g  brake: {min(view.ax):.3f} g\n"
        f"Peak |steer|: {max(abs(a) for a in view.steer):.2f} deg\n"
        f"{view.notes}\n"
    )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
