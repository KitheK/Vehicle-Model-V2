#!/usr/bin/env python3
"""Ranking save/sort/export (no libfastestlapc)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from fsae.qss_ranking import (  # noqa: E402
    build_record,
    delete_entry,
    downsample_aligned,
    export_car_xlsx,
    filter_by_map,
    load_entries,
    save_entry,
    sort_entries,
)
from fsae.xlsx_kit import detect_kind, list_car_fields  # noqa: E402
from fsae.openvehicle_xlsx import read_openvehicle_xlsx, write_ubco_2026_xlsx  # noqa: E402


def _channels(n: int = 50, ay_scale: float = 1.0) -> dict:
    return {
        "s": [float(i) for i in range(n)],
        "x": [float(i) for i in range(n)],
        "y": [0.0] * n,
        "time": [i * 0.1 for i in range(n)],
        "v": [20.0 + i * 0.1 for i in range(n)],
        "vmax": [30.0] * n,
        "kappa": [0.01] * n,
        "ax": [0.2] * n,
        "ay": [ay_scale] * n,
        "tps": [0.5] * n,
        "bps": [0.0] * n,
        "steer": [4.0] * n,
        "delta": [1.0] * n,
        "beta": [0.2] * n,
        "envAy": [0.0, 1.5],
        "envAxMax": [0.5, 0.0],
        "envAxMin": [-0.9, 0.0],
        "envSpeed": 15.0,
        "vehicle": "UBCO 2026 EV",
        "track": "2019 Endurance",
        "lapTime": n * 0.1,
    }


def _fields(mass: float, power: float = 80000.0) -> list:
    return [
        {"sheet": "Info", "description": "Name", "value": "UBCO 2026 EV", "category": "I", "unit": ""},
        {"sheet": "Info", "description": "Total Mass", "value": mass, "category": "I", "unit": "kg"},
        {"sheet": "Info", "description": "Maximum Power", "value": power, "category": "I", "unit": "W"},
    ]


def _summary(lap: float, track: str = "2019 Endurance") -> dict:
    return {
        "lap_time": lap,
        "vehicle": "UBCO 2026 EV",
        "track": track,
        "speed_kmh": {"min": 16.4, "mean": 65.1, "max": 138.3},
        "peak_ay_g": 1.65,
        "channels": _channels(),
    }


class TestQssRanking(unittest.TestCase):
    def test_downsample_shortens_aligned(self) -> None:
        long = {"s": list(range(1000)), "v": [float(i) for i in range(1000)]}
        out = downsample_aligned(long, max_points=400)
        self.assertEqual(len(out["s"]), 400)
        self.assertEqual(out["s"][0], 0)
        self.assertEqual(out["s"][-1], 999)
        self.assertEqual(out["v"][-1], 999.0)

    def test_save_sort_filter_delete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ranking.json"
            a = build_record(name="light", summary=_summary(120.0), car_fields=_fields(280), v_cap=40, synthetic=True)
            b = build_record(
                name="heavy",
                summary=_summary(110.0, track="Skidpad"),
                car_fields=_fields(320),
                v_cap=40,
                synthetic=True,
            )
            save_entry(path, a)
            save_entry(path, b)
            rows = load_entries(path)
            by_lap = sort_entries(rows, "lap_time")
            self.assertEqual(by_lap[0]["name"], "heavy")
            by_mass = sort_entries(rows, "mass")
            self.assertEqual(by_mass[0]["name"], "light")
            only = filter_by_map(rows, "Skidpad")
            self.assertEqual(len(only), 1)
            self.assertEqual(only[0]["name"], "heavy")
            self.assertTrue(delete_entry(path, b["id"]))
            self.assertEqual(len(load_entries(path)), 1)
            with self.assertRaises(ValueError):
                save_entry(path, build_record(name="light", summary=_summary(119.0), car_fields=_fields(280)))
            save_entry(
                path,
                build_record(name="light", summary=_summary(119.0), car_fields=_fields(275)),
                overwrite=True,
            )
            self.assertAlmostEqual(load_entries(path)[0]["car"]["mass"], 275.0)

    def test_empty_name_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_record(name="  ", summary=_summary(100.0), car_fields=_fields(290))

    def test_export_xlsx_mass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "ubco.xlsx"
            write_ubco_2026_xlsx(src)
            fields = list_car_fields(src)
            for item in fields:
                if item["description"] == "Total Mass":
                    item["value"] = 291.0
            entry = build_record(name="291 kg target", summary=_summary(117.2), car_fields=fields)
            dest = Path(tmp) / "out.xlsx"
            export_car_xlsx(entry, dest, template=src)
            self.assertEqual(detect_kind(dest), "car")
            data = read_openvehicle_xlsx(dest)
            self.assertAlmostEqual(data["mass"], 291.0)
            names = {f["description"]: f["value"] for f in list_car_fields(dest)}
            self.assertEqual(names["Name"], "291 kg target")

    def test_templates_have_ranking_nav(self) -> None:
        for name in ("qss_studio.html", "qss_hud.html", "qss_results.html", "qss_ranking.html"):
            text = (_HERE / name).read_text(encoding="utf-8")
            self.assertIn("ranking.html", text)
        ranking = (_HERE / "qss_ranking.html").read_text(encoding="utf-8")
        self.assertIn("Download .xlsx", ranking)
        self.assertIn("c-speed", ranking)
        studio = (_HERE / "qss_studio.html").read_text(encoding="utf-8")
        self.assertIn("Save to ranking", studio)
        self.assertIn("qss-last-run", studio)
        hud = (_HERE / "qss_hud.html").read_text(encoding="utf-8")
        self.assertIn("ghost", hud.lower())
        self.assertTrue("G." in hud or "ghost" in hud)


if __name__ == "__main__":
    unittest.main()
