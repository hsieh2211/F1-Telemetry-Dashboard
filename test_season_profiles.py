"""Cover season identity, export coverage, historical rosters and profile UI."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from season_profiles import load_profiles, snapshot_rows

ROOT = Path(__file__).resolve().parent


class SeasonProfileTests(unittest.TestCase):
    def test_profiles_cover_every_exported_driver_and_team_relationship(self):
        data = load_profiles(ROOT, 2026)
        self.assertEqual(len(data["teams"]), 11)
        self.assertEqual(len(data["drivers"]), 25)
        self.assertEqual(data["teams"]["cadillac"]["car"], "MAC-26")
        self.assertEqual(data["teams"]["aston-martin"]["power_unit"], "Honda")
        seen = set()
        for path in (ROOT / "data").glob("2026_*.json"):
            for driver in json.loads(path.read_text())["drivers"]:
                code = driver["code"]
                seen.add(code)
                self.assertIn(code, data["drivers"])
                if driver.get("team") not in (None, "", "None"):
                    self.assertIn(driver["team"], [data["teams"][t]["name"] for t in data["drivers"][code]["teams"]])
        self.assertEqual(seen, set(data["drivers"]))

    def test_display_never_overwrites_missing_snapshot_identity(self):
        snapshot = {"HIR": {"name": "None None", "team": "None"}, "LAW": {"name": "Liam Lawson", "team": "Red Bull Racing"}}
        original = copy.deepcopy(snapshot)
        rows = snapshot_rows(snapshot)
        self.assertEqual(snapshot, original)
        self.assertEqual(rows[0]["匯出姓名"], "未提供")
        self.assertEqual(rows[1]["匯出車隊"], "Red Bull Racing")
        data = load_profiles(ROOT, 2026)
        self.assertEqual(set(data["drivers"]["LAW"]["teams"]), {"racing-bulls", "red-bull-racing"})

    def test_wrong_or_absent_season_does_not_borrow_current_registry(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "data").mkdir()
            (root / "data/profiles_2026.json").write_text(json.dumps({"year": 2025}))
            with self.assertRaises(ValueError):
                load_profiles(root, 2026)
            with self.assertRaises(FileNotFoundError):
                load_profiles(ROOT, 2027)

    def test_offline_car_and_driver_views_follow_selected_event(self):
        with patch("fastf1.get_session", side_effect=AssertionError("offline only")):
            app = AppTest.from_file(str(ROOT / "demo.py"), default_timeout=30).run()
            app.selectbox(key="profile_team").set_value("cadillac").run()
            self.assertTrue(any(x.value == "MAC-26" for x in app.metric))
            app.radio(key="profile_focus").set_value("車手").run()
            app.selectbox(key="profile_driver").set_value("CAM").run()
            self.assertTrue(any("沒有 CAM" in x.value for x in app.info))
            app.selectbox(key="home_event").set_value(19).run()
            self.assertTrue(any("有 CAM 的名單紀錄" in x.value for x in app.info))
            app.selectbox(key="profile_driver").set_value("OCO").run()
            self.assertTrue(any("沒有 OCO" in x.value for x in app.info))
            app.selectbox(key="home_event").set_value(17).run()
            self.assertTrue(any("有 OCO 的名單紀錄" in x.value for x in app.info))
            self.assertFalse(app.exception)


if __name__ == "__main__":
    unittest.main()
