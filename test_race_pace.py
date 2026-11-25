"""Synthetic records are test-only; never shipped as race data."""
import copy
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from race_pace import export_laps, validate_laps, read_laps, laps_path, pace_rows, stint_summary
from export_data import run, atomic_json

IDENTITY = (2026, "Test Grand Prix", "R")


def fixture():
    rows = []
    for driver, extra in (("AAA", 0), ("BBB", 2)):
        for lap in range(1, 9):
            time = 90 + lap * .1 + extra
            rows.append({"Driver": driver, "LapNumber": lap, "LapTime": pd.Timedelta(seconds=time),
                "LapStartTime": pd.Timedelta(seconds=(lap - 1) * 100), "Time": pd.Timedelta(seconds=(lap - 1) * 100 + time),
                "Stint": 1 if lap < 5 else 2, "Compound": "MEDIUM" if lap < 5 else "HARD", "TyreLife": lap if lap < 5 else lap - 4,
                "Position": 1 if driver == "AAA" else 2, "IsAccurate": True, "Deleted": False,
                "FastF1Generated": False, "FreshTyre": lap in (1, 5), "TrackStatus": "1",
                "PitInTime": pd.Timedelta(seconds=390) if lap == 4 else pd.NaT,
                "PitOutTime": pd.Timedelta(seconds=420) if lap == 5 else pd.NaT})
    session = Mock()
    session.session_status = pd.DataFrame({"Status": ["Started", "Finished", "Finalised"]})
    session.results = pd.DataFrame([{"Abbreviation": c, "FullName": c + " Name", "TeamName": "Test Team"} for c in ("AAA", "BBB", "DNS")])
    session.laps = pd.DataFrame(rows)
    return session


class PaceTests(unittest.TestCase):
    def payload(self):
        return export_laps(fixture(), *IDENTITY, "test")

    def test_roundtrip_keeps_roster_missing_values_and_pit_times(self):
        payload = self.payload()
        self.assertEqual(len(payload["drivers"]), 3)
        self.assertEqual(len(payload["laps"]), 16)
        self.assertIsNone(payload["laps"][0]["sector1_seconds"])
        self.assertEqual(payload["laps"][3]["pit_in_seconds"], 390)
        self.assertEqual(payload["laps"][4]["pit_out_seconds"], 420)
        self.assertNotEqual(laps_path(Path("."), *IDENTITY).name, "2026_test_grand_prix_r.json")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "laps.json"
            atomic_json(path, payload)
            self.assertEqual(len(read_laps(path, IDENTITY)[1]), 16)

    def test_no_completion_or_qualifying_export(self):
        session = fixture()
        session.session_status = pd.DataFrame({"Status": ["Started", "Finished"]})
        with self.assertRaisesRegex(ValueError, "Finalised"):
            export_laps(session, *IDENTITY, "test")
        with self.assertRaises(ValueError):
            export_laps(fixture(), 2026, "Test Grand Prix", "Q", "test")

    def test_null_time_is_retained_but_not_used_for_pace(self):
        session = fixture()
        session.laps.loc[2, "LapTime"] = pd.NaT
        payload = export_laps(session, *IDENTITY, "test")
        self.assertEqual(len(payload["laps"]), 16)
        self.assertIsNone(payload["laps"][2]["lap_seconds"])
        selected = pace_rows(validate_laps(payload, IDENTITY)[1])
        self.assertIn("無圈速", selected.loc[2, "excluded_reason"])

    def test_exclusions_and_stint_medians_are_explicit(self):
        payload = self.payload()
        payload["laps"][1]["track_status"] = "12"
        payload["laps"][2]["deleted"] = None
        payload["laps"][5]["accurate"] = None
        payload["laps"][6]["generated"] = True
        frame = validate_laps(payload, IDENTITY)[1]
        annotated = pace_rows(frame)
        a = annotated[annotated.driver.eq("AAA")]
        self.assertEqual(a[a.included]["lap"].tolist(), [8])
        self.assertIn("刪圈狀態缺漏", a.iloc[2].excluded_reason)
        summary = stint_summary(frame)
        a2 = summary[(summary.driver == "AAA") & (summary.stint == 2)].iloc[0]
        self.assertEqual(a2.eligible_laps, 1)
        self.assertAlmostEqual(a2.median_seconds, 90.8)

    def test_corrupt_files_fail_closed(self):
        base = self.payload()
        for field, value in (("lap", 2.5), ("lap_seconds", float("nan")), ("accurate", "true"), ("position", -1)):
            with self.subTest(field=field):
                payload = copy.deepcopy(base)
                payload["laps"][0][field] = value
                with self.assertRaises(ValueError): validate_laps(payload, IDENTITY)
        for mutate in (lambda p: p["laps"].append(p["laps"][0]),
                       lambda p: p.update(year=2027), lambda p: p.update(session_finalised=False),
                       lambda p: p.update(exported_at="2026-01-01T00:00:00")):
            payload = copy.deepcopy(base)
            mutate(payload)
            with self.assertRaises(ValueError): validate_laps(payload, IDENTITY)

    def test_export_mode_keeps_fastest_file_and_resumes_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            atomic_json(root / "data/schedule_2026.json", {"year": 2026, "events": [{"event": IDENTITY[1], "sessions": {
                "R": {"start_utc": "2026-01-01T00:00:00Z"}, "Q": {"start_utc": "2025-12-31T00:00:00Z"}}}]})
            fastest = root / "data/2026_test_grand_prix_r.json"
            fastest.write_text('{"unchanged":true}')
            args = Namespace(year=2026, saved_schedule=True, event=IDENTITY[1], sessions=["R"], refresh=False, race_laps=True)
            fastf1 = Mock(__version__="test")
            fastf1.get_session.return_value = fixture()
            self.assertEqual(run(args, fastf1, root), 0)
            fastf1.get_session.return_value.load.assert_called_once_with(laps=True, telemetry=False, weather=False, messages=True)
            self.assertEqual(fastest.read_text(), '{"unchanged":true}')
            fastf1.get_session.reset_mock()
            self.assertEqual(run(args, fastf1, root), 0)
            fastf1.get_session.assert_not_called()
            # Failed refresh preserves the last valid lap file.
            before = laps_path(root, *IDENTITY).read_bytes()
            args.refresh = True
            fastf1.get_session.side_effect = RuntimeError("source unavailable")
            self.assertEqual(run(args, fastf1, root), 1)
            self.assertEqual(laps_path(root, *IDENTITY).read_bytes(), before)

    def test_ui_missing_and_valid_records_stay_offline(self):
        with tempfile.TemporaryDirectory() as directory, patch('fastf1.get_session', side_effect=AssertionError('offline')):
            root = Path(directory)
            script = f"from pathlib import Path\nfrom race_pace_ui import render_race_pace\nrender_race_pace(Path({str(root)!r}), {IDENTITY!r}, '測試資料')"
            app = AppTest.from_string(script, default_timeout=30).run()
            self.assertFalse(app.exception)
            self.assertTrue(any("尚未收錄" in x.value for x in app.info))
            atomic_json(laps_path(root, *IDENTITY), self.payload())
            app.run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.metric), 2)
            self.assertTrue(any("DNS" in c.value for c in app.caption))
            app.multiselect[0].set_value([]).run()
            self.assertFalse(app.exception)
            self.assertTrue(any("至少選擇" in x.value for x in app.info))


if __name__ == "__main__":
    unittest.main()
