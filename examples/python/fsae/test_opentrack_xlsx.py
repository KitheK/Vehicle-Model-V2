#!/usr/bin/env python3
"""OpenTRACK xlsx mesher tests."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from fsae.opentrack_xlsx import (  # noqa: E402
    TrackGeoref,
    TrackLocation,
    list_track_locations,
    mesh_opentrack,
    mesh_to_discrete_xml,
    project_official_line,
    read_official_line,
    write_fsae_skidpad_xlsx,
    write_map_xlsx,
)
from fsae.qss_lap import GGTable, qss_lap  # noqa: E402


class TestOpenTrackXlsx(unittest.TestCase):
    def test_skidpad_length_and_two_circles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            xlsx = Path(tmp) / "skidpad.xlsx"
            write_fsae_skidpad_xlsx(xlsx)
            mesh = mesh_opentrack(xlsx, mesh_size=1.0, half_width=1.5)
            self.assertAlmostEqual(mesh.length, 114.0, places=6)
            self.assertGreater(len(mesh.s), 100)
            xml = mesh_to_discrete_xml(mesh)
            self.assertIn('format="discrete"', xml)
            self.assertIn('type="closed"', xml)
            self.assertIn("<nl units=\"m\">", xml)
            kmax = max(mesh.kappa)
            kmin = min(mesh.kappa)
            self.assertGreater(kmax, 0.08)
            self.assertLess(kmin, -0.08)
            self.assertAlmostEqual(kmax, 1.0 / 9.125, delta=0.03)
            self.assertAlmostEqual(abs(kmin), 1.0 / 9.125, delta=0.03)

    def test_2019_endurance_closed_loop(self) -> None:
        path = Path(__file__).resolve().parents[3] / "database/tracks/fsae_2019_endurance/2019_endurance.xlsx"
        if not path.is_file():
            self.skipTest("2019_endurance.xlsx not in the tree")
        mesh = mesh_opentrack(path, mesh_size=1.0, half_width=1.5)
        self.assertEqual(mesh.info.name, "2019 Endurance")
        self.assertAlmostEqual(mesh.length, 1823.31, places=2)
        self.assertGreater(len(mesh.s), 1800)
        gap = ((mesh.x[-1] - mesh.x[0]) ** 2 + (mesh.y[-1] - mesh.y[0]) ** 2) ** 0.5
        self.assertLess(gap, 1.0e-6)
        xml = mesh_to_discrete_xml(mesh)
        self.assertIn('type="closed"', xml)
        self.assertGreater(max(abs(k) for k in mesh.kappa), 0.2)

    def test_official_skidpad_if_present(self) -> None:
        path = Path("/tmp/opentrack/FSAE Skidpad.xlsx")
        if not path.is_file():
            self.skipTest("official OpenTRACK FSAE Skidpad.xlsx not present")
        mesh = mesh_opentrack(path, mesh_size=1.0)
        self.assertEqual(mesh.info.name, "FSAE Skidpad")
        self.assertAlmostEqual(mesh.length, 114.0, places=6)

    def test_qss_lap_synthetic_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            xlsx = Path(tmp) / "skidpad.xlsx"
            write_fsae_skidpad_xlsx(xlsx)
            mesh = mesh_opentrack(xlsx, mesh_size=2.0)
            ay = [0.0, 0.5, 1.0, 1.5]
            ax_max = [0.4, 0.35, 0.25, 0.0]
            ax_min = [-0.8, -0.75, -0.6, 0.0]
            table = GGTable(
                speeds=[10.0, 20.0],
                ay=[ay, list(ay)],
                ax_max=[ax_max, list(ax_max)],
                ax_min=[ax_min, list(ax_min)],
            )
            result = qss_lap(mesh, table, v_cap=30.0)
            self.assertGreater(result.lap_time, 5.0)
            self.assertLess(result.lap_time, 20.0)
            self.assertEqual(len(result.v), len(mesh.s))
            self.assertTrue(all(v > 1.0 for v in result.v))

    def test_xlsx_locations_are_queryable_and_projectable(self) -> None:
        line = [[-84.24, 42.07], [-84.23, 42.07], [-84.23, 42.06], [-84.24, 42.07]]
        origin = TrackLocation("Home", "original", 42.07, -84.24, 0.0)
        alt = TrackLocation("Away", "alternate", 49.89, -119.50, 0.0)
        moved = project_official_line(line, origin, alt)
        self.assertEqual(len(moved), len(line))
        self.assertAlmostEqual(moved[0][1], alt.lat, places=5)
        self.assertAlmostEqual(moved[0][0], alt.lon, places=5)
        with tempfile.TemporaryDirectory() as tmp:
            xlsx = Path(tmp) / "track.xlsx"
            write_map_xlsx(
                xlsx,
                {"name": "Test", "country": "CA", "city": "Kelowna"},
                [("Straight", 10.0, 0.0), ("Left", 20.0, 15.0)],
                georef=TrackGeoref(
                    official_line=line,
                    locations=[origin, alt],
                    map_corners={"tl": [42.08, -84.22], "tr": [42.05, -84.22], "bl": [42.08, -84.26]},
                ),
            )
            self.assertEqual(len(read_official_line(xlsx)), 4)
            names = [loc.name for loc in list_track_locations(xlsx)]
            self.assertEqual(names, ["Home", "Away"])

    def test_mesh_scale_halves_length_and_doubles_kappa(self) -> None:
        """Uniform map scale must shrink length/radii and raise curvature for QSS."""
        with tempfile.TemporaryDirectory() as tmp:
            xlsx = Path(tmp) / "skidpad.xlsx"
            write_fsae_skidpad_xlsx(xlsx)
            full = mesh_opentrack(xlsx, mesh_size=1.0, half_width=1.5, scale=1.0)
            half = mesh_opentrack(xlsx, mesh_size=1.0, half_width=1.5, scale=0.5)
            self.assertAlmostEqual(half.length, full.length * 0.5, places=4)
            self.assertAlmostEqual(half.nl[0], 0.75, places=6)
            # Mean |κ| ~ doubles (peak can include closure spikes).
            mean_full = sum(abs(k) for k in full.kappa) / len(full.kappa)
            mean_half = sum(abs(k) for k in half.kappa) / len(half.kappa)
            self.assertAlmostEqual(mean_half, mean_full * 2.0, delta=0.02)

    def test_ev2026_mesh_matches_map_csv(self) -> None:
        """Constant-κ Shape rebuild stays congruent with the published map CSV."""
        import numpy as np
        from fsae.hud_georef import align_map_to_mesh, load_centerline_csv

        root = Path(__file__).resolve().parents[4]
        xlsx = (
            Path(__file__).resolve().parents[3]
            / "database/tracks/fsae_ev_2026_endurance/fsae_ev_2026_endurance.xlsx"
        )
        csv_path = root / "fsae-ev-endurance-map" / "official_ev_2026_endurance_1m.csv"
        if not xlsx.is_file():
            self.skipTest("fsae_ev_2026_endurance.xlsx not in the tree")
        if not csv_path.is_file():
            alt = xlsx.parent / "official_ev_2026_endurance_1m.csv"
            if alt.is_file():
                csv_path = alt
            else:
                self.skipTest("official_ev_2026_endurance_1m.csv not found")
        mesh = mesh_opentrack(xlsx, mesh_size=1.0)
        s, cx, cy = load_centerline_csv(csv_path)
        align = align_map_to_mesh(cx, cy, np.asarray(mesh.x), np.asarray(mesh.y))
        self.assertLess(float(align["rms_m"]), 2.0)
        self.assertAlmostEqual(mesh.length, float(s[-1]), delta=3.0)

    def test_qss_lap_from_rest_starts_near_zero(self) -> None:
        from fsae.opentrack_xlsx import OpenTrackInfo, write_map_xlsx

        with tempfile.TemporaryDirectory() as tmp:
            xlsx = Path(tmp) / "straight.xlsx"
            write_map_xlsx(
                xlsx,
                OpenTrackInfo(name="Accel", configuration="Open"),
                [("Straight", 400.0, 0.0)],
            )
            mesh = mesh_opentrack(xlsx, mesh_size=5.0)
            ay = [0.0, 0.5, 1.0]
            table = GGTable(
                speeds=[15.0],
                ay=[ay],
                ax_max=[[0.50, 0.40, 0.20]],
                ax_min=[[-0.90, -0.70, -0.30]],
            )
            flying = qss_lap(mesh, table, v_cap=40.0, from_rest=False)
            standing = qss_lap(mesh, table, v_cap=40.0, from_rest=True)
            self.assertLess(standing.v[0], 1.0)
            self.assertGreater(flying.v[0], 10.0)
            self.assertGreater(max(standing.v) * 3.6, 100.0)
            self.assertGreater(standing.lap_time, flying.lap_time)


if __name__ == "__main__":
    unittest.main()
