#!/usr/bin/env python3
"""Standard Car / Map / Driver .xlsx round-trips."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from fsae.opentrack_xlsx import write_fsae_skidpad_xlsx  # noqa: E402
from fsae.openvehicle_xlsx import write_ubco_2026_xlsx  # noqa: E402
from fsae.qss_channels import reconstruct_lap  # noqa: E402
from fsae.qss_lap import GGTable, qss_lap  # noqa: E402
from fsae.opentrack_xlsx import mesh_opentrack  # noqa: E402
from fsae.xlsx_kit import (  # noqa: E402
    DRIVER_COLUMNS,
    convert_xlsx,
    detect_kind,
    read_driver_xlsx,
    write_driver_xlsx,
)


def _table() -> GGTable:
    ay = [0.0, 0.8, 1.5]
    return GGTable(
        speeds=[15.0],
        ay=[ay],
        ax_max=[[0.45, 0.28, 0.0]],
        ax_min=[[-0.85, -0.55, 0.0]],
    )


class TestXlsxKit(unittest.TestCase):
    def test_detect_kind_car_map_driver(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            car = Path(tmp) / "car.xlsx"
            track = Path(tmp) / "map.xlsx"
            write_ubco_2026_xlsx(car)
            write_fsae_skidpad_xlsx(track)
            self.assertEqual(detect_kind(car), "car")
            self.assertEqual(detect_kind(track), "map")

    def test_ubco_and_2019_endurance_on_disk(self) -> None:
        root = Path(__file__).resolve().parents[3]
        car = root / "database/vehicles/fsae/ubco-2026-ev.xlsx"
        track = root / "database/tracks/fsae_2019_endurance/2019_endurance.xlsx"
        if not car.is_file() or not track.is_file():
            self.skipTest("database workbooks not in the tree")
        self.assertEqual(detect_kind(car), "car")
        self.assertEqual(detect_kind(track), "map")

    def test_driver_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            xlsx = Path(tmp) / "skidpad.xlsx"
            write_fsae_skidpad_xlsx(xlsx)
            mesh = mesh_opentrack(xlsx, mesh_size=2.0)
            result = qss_lap(mesh, _table(), v_cap=30.0)
            view = reconstruct_lap(
                result, mesh, _table(), vehicle_name="Test EV", track_name="FSAE Skidpad"
            )
            driver = Path(tmp) / "driver.xlsx"
            write_driver_xlsx(view, driver)
            self.assertEqual(detect_kind(driver), "driver")
            data = read_driver_xlsx(driver)
            self.assertEqual(data["info"]["Vehicle"], "Test EV")
            self.assertEqual(len(data["channels"]["distance_m"]), len(view.s))
            self.assertAlmostEqual(data["channels"]["speed_mps"][0], view.v[0], places=6)
            self.assertAlmostEqual(data["channels"]["LonAcc_g"][10], view.ax[10], places=6)
            names = [n for n, _ in DRIVER_COLUMNS]
            for name in names:
                self.assertIn(name, data["channels"])
            convert_xlsx(driver)

    def test_convert_car_and_map(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            car = Path(tmp) / "car.xlsx"
            track = Path(tmp) / "map.xlsx"
            write_ubco_2026_xlsx(car)
            write_fsae_skidpad_xlsx(track)
            xml_car = convert_xlsx(car, Path(tmp) / "car.xml")
            xml_map = convert_xlsx(track, Path(tmp) / "map.xml")
            self.assertIn("fsae-6dof", xml_car.read_text(encoding="utf-8"))
            self.assertIn('format="discrete"', xml_map.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
