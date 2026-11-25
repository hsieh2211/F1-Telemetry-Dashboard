"""Review regressions: shared driver context and independent view summaries."""
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from analysis_charts import pace_charts
from analysis_theme import PALETTE
from race_pace import pace_rows, validate_laps
from test_race_pace import fixture, IDENTITY
from race_pace import export_laps

ROOT = Path(__file__).resolve().parent
EXTRA = "pace_extra_2026_Las Vegas Grand Prix_R"


class AnalysisDesignTests(unittest.TestCase):
    def app(self):
        app = AppTest.from_file(str(ROOT / "demo.py"), default_timeout=30)
        for key, value in dict(page="analysis", event_index=20, session_code="R", analysis_a="ANT", analysis_b="LEC").items():
            app.session_state[key] = value
        return app

    def test_shared_pair_and_scoped_summaries(self):
        with patch("fastf1.get_session", side_effect=AssertionError("offline")):
            app = self.app().run()
            self.assertFalse(app.exception)
            self.assertEqual([tab.label for tab in app.tabs], ["最快圈比對", "整場節奏與輪胎", "單圈資料"])
            self.assertEqual(len(app.tabs[0].metric), 3)
            self.assertEqual([m.label for m in app.tabs[1].metric], ["ANT 有效圈中位數", "LEC 有效圈中位數"])
            self.assertFalse(any("最快圈" in m.label for m in app.tabs[1].metric))
            app.selectbox(key="analysis_b").set_value("NOR").run()
            self.assertFalse(app.exception)
            self.assertEqual([m.label for m in app.tabs[1].metric], ["ANT 有效圈中位數", "NOR 有效圈中位數"])
            self.assertTrue(any("B｜NOR" in m.label for m in app.tabs[0].metric))

    def test_extra_selection_deduplicates_when_shared_pair_changes(self):
        app = self.app().run()
        app.multiselect(key=EXTRA).set_value(["NOR", "VER"]).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.tabs[1].metric), 4)
        app.selectbox(key="analysis_a").set_value("NOR").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.multiselect(key=EXTRA).value, ["VER"])
        self.assertEqual([m.label for m in app.tabs[1].metric], ["NOR 有效圈中位數", "LEC 有效圈中位數", "VER 有效圈中位數"])

    def test_missing_driver_laps_do_not_replace_the_shared_selection(self):
        app = self.app().run()
        app.selectbox(key="analysis_a").set_value("ALB").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key="analysis_a").value, "ALB")
        self.assertEqual([m.label for m in app.tabs[1].metric], ["LEC 有效圈中位數"])
        self.assertTrue(any("ALB 沒有逐圈紀錄" in i.value for i in app.tabs[1].info))

    def test_chart_preserves_gaps_and_exclusion_reasons(self):
        payload = export_laps(fixture(), *IDENTITY, "test")
        frame = validate_laps(payload, IDENTITY)[1]
        frame = frame[~((frame.driver == "AAA") & (frame.lap == 7))]
        annotated = pace_rows(frame)
        curve, exclusions = pace_charts(annotated, ["AAA", "BBB"], {"AAA": PALETTE[0], "BBB": PALETTE[1]}, 1, 8)
        spec = curve.to_dict()
        records = next(iter(spec["datasets"].values()))
        a = {r["lap"]: r for r in records if r["driver"] == "AAA"}
        self.assertNotEqual(a[6]["segment_id"], a[8]["segment_id"])
        omitted = next(iter(exclusions.to_dict()["datasets"].values()))
        self.assertTrue(any("進出站圈" in r["excluded_reason"] for r in omitted))
        self.assertIn("排除原因", str(exclusions.to_dict()["encoding"]["tooltip"]))


if __name__ == "__main__":
    unittest.main()
