#!/usr/bin/env python3
"""Studio defaults, car patching, and QSS job (no libfastestlapc)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from fsae.opentrack_xlsx import mesh_opentrack, write_fsae_skidpad_xlsx, write_map_xlsx  # noqa: E402
from fsae.openvehicle_xlsx import read_openvehicle_xlsx, write_ubco_2026_xlsx  # noqa: E402
from fsae.qss_job import defaults_payload, run_qss_job, synthetic_gg  # noqa: E402
from fsae.xlsx_kit import gg_from_driver_xlsx, list_car_fields, patch_car_xlsx, write_driver_xlsx  # noqa: E402
from fsae.qss_channels import reconstruct_lap  # noqa: E402
from fsae.qss_lap import qss_lap  # noqa: E402


class TestQssStudio(unittest.TestCase):
    def test_list_and_patch_car_mass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "car.xlsx"
            dst = Path(tmp) / "patched.xlsx"
            write_ubco_2026_xlsx(src)
            fields = list_car_fields(src)
            names = {f["description"] for f in fields}
            self.assertIn("Total Mass", names)
            self.assertIn("Maximum Power", names)
            patch_car_xlsx(src, dst, [{"sheet": "Info", "description": "Total Mass", "value": 290.0}])
            data = read_openvehicle_xlsx(dst)
            self.assertAlmostEqual(data["mass"], 290.0)

    def test_write_map_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "map.xlsx"
            write_map_xlsx(
                path,
                {"name": "Unit Track", "country": "CA", "type": "Temporary", "configuration": "Closed"},
                (("Straight", 10.0, 0.0), ("Left", 20.0, 8.0)),
            )
            mesh = mesh_opentrack(path, mesh_size=1.0)
            self.assertEqual(mesh.info.name, "Unit Track")
            self.assertAlmostEqual(mesh.length, 30.0, places=6)

    def test_job_writes_studio_and_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            track = Path(tmp) / "skidpad.xlsx"
            car = Path(tmp) / "car.xlsx"
            out = Path(tmp) / "out"
            write_fsae_skidpad_xlsx(track)
            write_ubco_2026_xlsx(car)
            summary = run_qss_job(car, track, out, synthetic=True, plots=False, v_cap=30.0)
            self.assertGreater(summary["lap_time"], 5.0)
            self.assertLess(summary["lap_time"], 40.0)
            self.assertTrue((out / "hud.html").is_file())
            self.assertTrue((out / "results.html").is_file())
            self.assertTrue((out / "studio.html").is_file())
            self.assertTrue((out / "driver.xlsx").is_file())
            self.assertIn("studio.html", (out / "hud.html").read_text(encoding="utf-8"))
            table = gg_from_driver_xlsx(out / "driver.xlsx")
            self.assertIsNotNone(table)
            self.assertGreaterEqual(len(table.ay[0]), 2)

    def test_driver_envelope_changes_lap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            track = Path(tmp) / "skidpad.xlsx"
            write_fsae_skidpad_xlsx(track)
            mesh = mesh_opentrack(track, mesh_size=2.0)
            weak = synthetic_gg()
            weak.ax_max = [[0.05, 0.04, 0.03, 0.02, 0.0]]
            result = qss_lap(mesh, weak, v_cap=20.0)
            view = reconstruct_lap(result, mesh, weak, track_name=mesh.info.name)
            driver = Path(tmp) / "driver.xlsx"
            write_driver_xlsx(view, driver)
            car = Path(tmp) / "car.xlsx"
            write_ubco_2026_xlsx(car)
            summary = run_qss_job(
                car, track, Path(tmp) / "out", driver_xlsx=driver, synthetic=True, plots=False, v_cap=20.0
            )
            self.assertGreater(summary["lap_time"], result.lap_time - 1.0)

    def test_defaults_payload_ubco(self) -> None:
        data = defaults_payload(Path("missing-out"))
        if not data["car"]["fields"]:
            self.skipTest("UBCO workbook not in the tree")
        self.assertTrue(any(f["description"] == "Total Mass" for f in data["car"]["fields"]))
        self.assertGreater(data["map"]["length_m"], 1800.0)

    def test_preview_skidpad_map(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "skidpad.xlsx"
            write_fsae_skidpad_xlsx(path)
            from fsae.xlsx_kit import preview_workbook

            data = preview_workbook(path)
            self.assertEqual(data["kind"], "map")
            self.assertEqual(data["name"], "FSAE Skidpad")
            self.assertAlmostEqual(data["length_m"], 114.0, places=6)
            self.assertEqual(len(data["shape"]), 6)


if __name__ == "__main__":
    unittest.main()
