"""Check real offline data, navigation handoff and graceful failures."""
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from homepage import taipei_time

ROOT = Path(__file__).resolve().parent


class HomepageTests(unittest.TestCase):
    def app(self):
        return AppTest.from_file(str(ROOT / "demo.py"), default_timeout=30)

    def test_real_case_and_depths(self):
        with patch("fastf1.get_session", side_effect=AssertionError("offline only")):
            app = self.app().run()
            self.assertFalse(app.exception)
            self.assertTrue(any("22 位" in x.value for x in app.success))
            self.assertEqual(len(app.selectbox(key="case_a").options), 22)
            app.radio(key="case_depth").set_value("看判讀").run()
            self.assertTrue(any("油量" in x.value for x in app.markdown))
            app.radio(key="case_depth").set_value("查方法").run()
            self.assertTrue(any("取樣點數" in x.value for x in app.markdown))

    def test_analysis_handoff_and_return(self):
        app = self.app().run()
        app.selectbox(key="home_session").set_value("Q").run()
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["page"], "analysis")
        self.assertEqual(app.selectbox(key="session_code").value, "Q")
        self.assertIn("United States", app.selectbox(key="event_index").options[app.selectbox(key="event_index").value])
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["page"], "home")

    def test_missing_and_corrupt_data_keep_beginner_content(self):
        for target, effect in (("homepage.existing_path", None), ("homepage.read_payload", ValueError("broken"))):
            with self.subTest(target=target):
                kwargs = {"return_value": ROOT / "not-present.json"} if effect is None else {"side_effect": effect}
                with patch(target, **kwargs):
                    app = self.app().run()
                self.assertFalse(app.exception)
                self.assertTrue(any("第一次看 F1" in x.value for x in app.header))
                self.assertFalse(app.button)

    def test_same_driver_does_not_invent_comparison(self):
        app = self.app().run()
        app.selectbox(key="case_b").set_value(app.selectbox(key="case_a").value).run()
        self.assertFalse(app.exception)
        self.assertTrue(any("不同車手" in x.value for x in app.info))

    def test_taiwan_export_time(self):
        self.assertEqual(taipei_time("2026-10-26T06:33:40+00:00"), "2026/10/26 14:33（台灣時間）")
        self.assertEqual(taipei_time(None), "未提供")
        self.assertEqual(taipei_time("broken"), "時間格式無效")


if __name__ == "__main__":
    unittest.main()
