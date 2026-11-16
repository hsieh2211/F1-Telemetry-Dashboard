"""Season isolation, honest comparison warnings, and sample-preserving zoom."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from season_content import comparison_flags, load_season_content, window_samples

ROOT = Path(__file__).resolve().parent


class SeasonContentTests(unittest.TestCase):
    def test_season_mismatch_and_absent_year_never_fall_back(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "data").mkdir()
            (root / "data/learning_2026.json").write_text(json.dumps({"year": 2025}))
            with self.assertRaises(ValueError):
                load_season_content(root, 2026, "learning")
            with self.assertRaises(FileNotFoundError):
                load_season_content(root, 2027, "learning")
            with self.assertRaises(ValueError):
                load_season_content(root, 2026, "../learning")

    def test_missing_and_different_conditions(self):
        a = {"compound": "SOFT", "tyre_life": None, "lap_number": 10}
        b = {"compound": "MEDIUM", "tyre_life": 4, "lap_number": 11}
        notes = comparison_flags(a, b)
        self.assertEqual(len(notes), 3)
        self.assertIn("缺資料", notes[1])
        b.update(a, tyre_life=0)
        self.assertEqual(comparison_flags(b, b), [])

    def test_zoom_preserves_original_samples_and_endpoints(self):
        data = pd.DataFrame({"Distance": [0., 10., 20., 30.], "Speed": [90., 100., 95., 105.]})
        selected = window_samples(data, "後 1/3")
        self.assertEqual(selected.Distance.tolist(), [20., 30.])
        pd.testing.assert_frame_equal(window_samples(data, "整圈"), data)
        pd.testing.assert_frame_equal(selected, data.iloc[2:])
        self.assertEqual(len(data), 4)

    def test_offline_levels_zoom_and_brazil_missing_tyre_life(self):
        with patch("fastf1.get_session", side_effect=AssertionError("offline only")):
            app = AppTest.from_file(str(ROOT / "demo.py"), default_timeout=30).run()
            for depth in ("常看比賽", "深入查核", "第一次看"):
                app.radio(key="guide_depth").set_value(depth).run()
                self.assertFalse(app.exception)
            for window in ("前 1/3", "中 1/3", "後 1/3"):
                app.selectbox(key="case_window").set_value(window).run()
                self.assertFalse(app.exception)
            app.selectbox(key="home_event").set_value(19).run()
            app.selectbox(key="case_a").set_value("STR").run()
            app.radio(key="case_depth").set_value("看判讀").run()
            self.assertTrue(any("胎齡缺資料" in x.value for x in app.warning))
            self.assertTrue(any("Overtake Mode" in x.value for x in app.markdown))
            self.assertFalse(app.exception)

    def test_sparse_window_shows_message_instead_of_inventing_samples(self):
        empty = pd.DataFrame(columns=["Distance", "Speed", "Throttle", "Brake", "Driver"])
        with patch("homepage.window_samples", return_value=empty):
            app = AppTest.from_file(str(ROOT / "demo.py"), default_timeout=30).run()
            self.assertFalse(app.exception)
            self.assertTrue(any("沒有足夠的兩車取樣" in x.value for x in app.info))


if __name__ == "__main__":
    unittest.main()
