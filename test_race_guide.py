"""Verify calendar boundaries and offline guide integration."""
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from race_data import read_catalogue
from race_guide import load_guides, next_race, start_label

ROOT = Path(__file__).resolve().parent


class RaceGuideTests(unittest.TestCase):
    def test_taiwan_date_rollover_and_weekday(self):
        self.assertEqual(start_label("2026-11-07T18:00:00Z"), "2026/11/08（日） 02:00")
        self.assertEqual(start_label("2026-11-22T04:00:00Z"), "2026/11/22（日） 12:00")
        self.assertEqual(start_label("2026-11-29T16:00:00Z"), "2026/11/30（一） 00:00")
        self.assertEqual(start_label(None), "時間待公布")
        with self.assertRaises(ValueError):
            start_label("2026-11-22T04:00:00")

    def test_next_race_boundary_and_end_of_season(self):
        events = read_catalogue(ROOT / "data/schedule_2026.json")["events"]
        self.assertEqual(next_race(events[::-1], datetime(2026, 11, 14, tzinfo=timezone.utc))["event"], "Las Vegas Grand Prix")
        self.assertEqual(next_race(events, datetime(2026, 11, 22, 4, tzinfo=timezone.utc))["event"], "Qatar Grand Prix")
        self.assertIsNone(next_race(events, datetime(2026, 12, 6, 13, tzinfo=timezone.utc)))

    def test_all_catalogue_events_have_guide_and_six_sprints(self):
        events = read_catalogue(ROOT / "data/schedule_2026.json")["events"]
        guides = load_guides(ROOT)["events"]
        self.assertEqual(set(guides), {e["event"] for e in events})
        self.assertEqual(sum("S" in e["sessions"] for e in events), 6)
        for guide in guides.values():
            self.assertEqual(len(guide["watch"]), 2)
            self.assertTrue(guide["source"].startswith("https://www.formula1.com/en/racing/2026/"))
        self.assertIn("Sepang", guides["Bahrain Grand Prix"]["venue"])
        self.assertIn("Madring", guides["Spanish Grand Prix"]["venue"])

    def test_missing_export_still_shows_upcoming_guide(self):
        with patch("fastf1.get_session", side_effect=AssertionError("offline only")):
            app = AppTest.from_file(str(ROOT / "demo.py"), default_timeout=30).run()
            app.selectbox(key="home_event").set_value(20).run()
            self.assertFalse(app.exception)
            self.assertTrue(any("Las Vegas Strip" in x.value for x in app.markdown))
            self.assertTrue(any("尚無離線資料" in x.value for x in app.info))
            self.assertTrue(any("第一次看 F1" in x.value for x in app.header))

    def test_brazil_switch_preserves_analysis_and_missing_details(self):
        with patch("fastf1.get_session", side_effect=AssertionError("offline only")):
            app = AppTest.from_file(str(ROOT / "demo.py"), default_timeout=30).run()
            app.selectbox(key="home_event").set_value(19).run()
            self.assertFalse(app.exception)
            self.assertTrue(any("21 位可比較" in x.value for x in app.success))
            self.assertTrue(any("STR：胎齡未提供" in x.value for x in app.markdown))
            app.selectbox(key="home_session").set_value("Q").run()
            self.assertTrue(any("22 位可比較" in x.value for x in app.success))
            app.button(key="home_analysis").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.selectbox(key="session_code").value, "Q")
            self.assertEqual(app.selectbox(key="event_index").value, 19)


if __name__ == "__main__":
    unittest.main()
