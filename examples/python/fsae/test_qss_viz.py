#!/usr/bin/env python3
"""QSS channel reconstruction and visualization tests (no libfastestlapc)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from fsae.opentrack_xlsx import mesh_opentrack, write_fsae_skidpad_xlsx  # noqa: E402
from fsae.qss_channels import bicycle_steer, reconstruct_lap  # noqa: E402
from fsae.qss_lap import GGTable, qss_lap  # noqa: E402
from fsae.qss_viz import (  # noqa: E402
    load_geo_map,
    plot_hud_frame,
    plot_openlap_results,
    write_hud_html,
    write_results_html,
)


class _HudStructureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str | None] = []
        self.parents: dict[str, str | None] = {}
        self.wheels: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        node_id = values.get("id")
        parent = next((item for item in reversed(self.stack) if item), None)
        if node_id:
            self.parents[node_id] = parent
        if values.get("data-wheel"):
            self.wheels.append(values["data-wheel"] or "")
        if tag not in {"meta", "link", "input", "br", "img", "hr"}:
            self.stack.append(node_id)

    def handle_endtag(self, tag: str) -> None:
        if tag not in {"meta", "link", "input", "br", "img", "hr"} and self.stack:
            self.stack.pop()


def _table() -> GGTable:
    ay = [0.0, 0.8, 1.5]
    return GGTable(
        speeds=[15.0],
        ay=[ay],
        ax_max=[[0.45, 0.28, 0.0]],
        ax_min=[[-0.85, -0.55, 0.0]],
    )


class TestQssViz(unittest.TestCase):
    def test_vehicle_dynamics_is_a_separate_side_panel_card(self) -> None:
        parser = _HudStructureParser()
        parser.feed((Path(__file__).with_name("qss_hud.html")).read_text(encoding="utf-8"))
        self.assertEqual(parser.parents.get("dynamics-card"), "side")
        self.assertEqual(parser.parents.get("dynamics-overlay"), "dynamics-card")
        self.assertEqual(parser.parents.get("car3d"), "dynamics-overlay")
        self.assertEqual(sorted(parser.wheels), ["fl", "fr", "rl", "rr"])

    def test_bicycle_steer_grows_with_curvature(self) -> None:
        s0, d0, _ = bicycle_steer(12.0, 0.0, 277.0, 1.62, 0.51, 800.0, 1000.0, 5.0)
        s1, d1, b1 = bicycle_steer(12.0, 1.0 / 9.125, 277.0, 1.62, 0.51, 800.0, 1000.0, 5.0)
        self.assertAlmostEqual(d0, 0.0, places=6)
        self.assertGreater(abs(d1), 5.0)
        self.assertGreater(abs(s1), abs(d1))
        self.assertTrue(abs(b1) < 30.0)

    def test_reconstructed_channels_on_skidpad(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            xlsx = Path(tmp) / "skidpad.xlsx"
            write_fsae_skidpad_xlsx(xlsx)
            mesh = mesh_opentrack(xlsx, mesh_size=2.0)
            result = qss_lap(mesh, _table(), v_cap=30.0)
            view = reconstruct_lap(result, mesh, _table(), track_name=mesh.info.name)
            self.assertEqual(len(view.tps), len(mesh.s))
            self.assertTrue(all(0.0 <= x <= 1.0 for x in view.tps))
            self.assertTrue(all(0.0 <= x <= 1.0 for x in view.bps))
            self.assertGreater(max(abs(a) for a in view.delta), 5.0)
            self.assertGreater(max(abs(a) for a in view.ay), 0.8)
            self.assertEqual(len(view.energy_fl), len(mesh.s))
            self.assertGreaterEqual(view.energy_fl[-1], view.energy_fl[0])

    def test_artifacts_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            xlsx = Path(tmp) / "skidpad.xlsx"
            out = Path(tmp) / "out"
            write_fsae_skidpad_xlsx(xlsx)
            mesh = mesh_opentrack(xlsx, mesh_size=2.0)
            result = qss_lap(mesh, _table(), v_cap=30.0)
            view = reconstruct_lap(
                result, mesh, _table(), vehicle_name="Test EV", track_name="FSAE Skidpad"
            )
            png1 = plot_openlap_results(view, out / "openlap_results.png")
            png2 = plot_hud_frame(view, out / "hud_frame.png", index=10)
            html = write_hud_html(view, out / "hud.html")
            results = write_results_html(view, out / "results.html")
            self.assertGreater(png1.stat().st_size, 10_000)
            self.assertGreater(png2.stat().st_size, 10_000)
            text = html.read_text(encoding="utf-8")
            self.assertIn("canvas", text)
            self.assertIn("FSAE Skidpad", text)
            self.assertIn("requestAnimationFrame", text)
            self.assertIn("drawUbcoCar", text)
            self.assertIn("emptyCar", text)
            self.assertIn("let playing = !D.fromRest", text)
            self.assertIn('"fromRest":false', text)
            self.assertNotIn("let trackCar = buildUbcoCar()", text)
            self.assertNotIn("keeping procedural car", text)
            self.assertNotIn("function buildUbcoCar(", text)
            self.assertIn("zoom-in", text)
            self.assertIn("setCamHeight", text)
            self.assertIn("D.xl", text)
            self.assertIn("grid-template-columns: 1fr 380px", text)
            self.assertIn("overflow-y:auto", text)
            self.assertIn("Tires", text)
            self.assertIn("tire-fl", text)
            self.assertIn("Fz", text)
            self.assertIn("drawDriver", text)
            self.assertIn("TPS", text)
            self.assertIn("BPS", text)
            self.assertIn("telem-filters", text)
            self.assertIn('data-ch="v"', text)
            self.assertIn('data-ch="tps"', text)
            self.assertIn("no channels selected", text)
            self.assertIn("addEventListener('input'", text)
            self.assertIn("addEventListener('change'", text)
            self.assertIn("setLineDash([1.6, 1.4])", text)
            self.assertIn("translate(w/2, h/2)", text)
            self.assertIn("leaflet.js", text)
            self.assertIn("leaflet.css", text)
            self.assertIn("USE_GEO", text)
            self.assertIn("initLeafletStage", text)
            self.assertIn("CAR_MIN_PX", text)
            self.assertNotIn("Math.PI/2 - yaw", text)
            self.assertIn(str(round(view.lap_time, 3)).split(".")[0], text)
            self.assertIn("results.html", text)
            self.assertIn("studio.html", text)
            self.assertIn("ranking.html", text)
            self.assertIn("GLTFLoader", text)
            self.assertIn("loadCarModel", text)
            self.assertIn("MODEL_PATH", text)
            self.assertIn("car.glb", text)
            self.assertNotIn("applyNeutralMaterials", text)
            matlab = results.read_text(encoding="utf-8")
            self.assertIn("LonAcc", matlab)
            self.assertIn("c-kappa", matlab)
            self.assertIn("GGV usage", matlab)
            self.assertIn('"kappa":', matlab)
            self.assertIn("ranking.html", matlab)

    def test_ev2026_hud_payload_has_official_line(self) -> None:
        track_dir = (
            Path(__file__).resolve().parents[3]
            / "database/tracks/fsae_ev_2026_endurance"
        )
        xlsx = track_dir / "fsae_ev_2026_endurance.xlsx"
        if not xlsx.is_file():
            self.skipTest("fsae_ev_2026_endurance.xlsx not in the tree")
        geo = load_geo_map(track_dir)
        self.assertIsNotNone(geo)
        self.assertGreaterEqual(len(geo["officialLine"]), 2)
        self.assertIn("tl", geo["mapCorners"])
        self.assertIn("locations", geo)
        self.assertGreaterEqual(len(geo["locations"]), 1)
        ubco = load_geo_map(track_dir, location="UBCO Lot H")
        if ubco and any(l["name"] == "UBCO Lot H" for l in geo["locations"]):
            self.assertEqual(ubco["activeLocation"], "UBCO Lot H")
            self.assertAlmostEqual(ubco["mapCenter"][0], 49.942079, places=4)
            self.assertAlmostEqual(ubco["mapCenter"][1], -119.392312, places=4)
        with tempfile.TemporaryDirectory() as tmp:
            mesh = mesh_opentrack(xlsx, mesh_size=5.0)
            result = qss_lap(mesh, _table(), v_cap=30.0)
            view = reconstruct_lap(
                result, mesh, _table(), vehicle_name="UBCO EV", track_name=mesh.info.name
            )
            html = write_hud_html(view, Path(tmp) / "hud.html", track_dir=track_dir)
            text = html.read_text(encoding="utf-8")
            self.assertIn('"officialLine":', text)
            self.assertIn('"mapCorners":', text)
            self.assertIn('"locations":', text)
            self.assertIn("site-search", text)
            self.assertIn("searchAndGo", text)
            self.assertIn("geocodePlace", text)
            self.assertIn("famousMaps", text)
            self.assertIn("course-map", text)
            self.assertIn("map-scale", text)
            self.assertIn("selectFamousMap", text)
            self.assertNotIn('"ground":', text)
            self.assertIn("World_Imagery", text)

    def test_2019_endurance_qss_artifacts(self) -> None:
        xlsx = Path(__file__).resolve().parents[3] / "database/tracks/fsae_2019_endurance/2019_endurance.xlsx"
        if not xlsx.is_file():
            self.skipTest("2019_endurance.xlsx not in the tree")
        with tempfile.TemporaryDirectory() as tmp:
            mesh = mesh_opentrack(xlsx, mesh_size=5.0)
            result = qss_lap(mesh, _table(), v_cap=30.0)
            self.assertGreater(result.lap_time, 40.0)
            self.assertLess(result.lap_time, 400.0)
            view = reconstruct_lap(
                result, mesh, _table(), vehicle_name="UBCO 2026 EV", track_name=mesh.info.name
            )
            html = write_hud_html(view, Path(tmp) / "hud.html")
            text = html.read_text(encoding="utf-8")
            self.assertIn("2019 Endurance", text)
            self.assertIn("drawUbcoCar", text)
            self.assertIn("car.glb", text)
            self.assertIn("Tires", text)
            self.assertIn("tire-fl", text)
            self.assertGreater(max(view.s), 1800.0)


if __name__ == "__main__":
    unittest.main()
