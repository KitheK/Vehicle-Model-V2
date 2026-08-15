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
    mesh_opentrack,
    mesh_to_discrete_xml,
    write_fsae_skidpad_xlsx,
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


if __name__ == "__main__":
    unittest.main()
