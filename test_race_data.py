import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from argparse import Namespace

from race_data import (read_catalogue, read_payload, session_state,
                       validate_payload, existing_path, data_path)
from export_data import atomic_json, compact_telemetry, run, export_session

ROOT = Path(__file__).resolve().parent


class DataTests(unittest.TestCase):
    def test_schedule(self):
        schedule = read_catalogue(ROOT / 'data/schedule_2026.json')
        self.assertGreater(len(schedule['events']), 20)
        self.assertEqual(set(schedule['events'][0]['sessions']), {'R', 'Q'})
        sprint_events = {
            event['event'] for event in schedule['events']
            if 'S' in event['sessions']
        }
        self.assertTrue({
            'Chinese Grand Prix', 'Miami Grand Prix', 'Canadian Grand Prix'
        }.issubset(sprint_events))

    def test_future_waiting_missing_unknown(self):
        now = datetime(2026, 9, 17, tzinfo=timezone.utc)
        for start, expected in [('2026-09-18T00:00:00Z', 'future'),
                                ('2026-09-17T00:00:00Z', 'waiting'),
                                ('2026-09-16T00:00:00Z', 'missing'), (None, 'unknown')]:
            self.assertEqual(session_state(start, now)[0], expected)
        with self.assertRaises(ValueError):
            session_state('2026-09-17T00:00:00', now)

    def test_existing_australia(self):
        for code in ('R', 'Q'):
            path = existing_path(ROOT, 2026, 'Australian Grand Prix', code)
            result = read_payload(path, (2026, 'Australian Grand Prix', code))
            self.assertEqual(len(result[3]), 22)
            available = [driver for driver in result[3].values() if driver['available']]
            self.assertTrue(all(driver['lap_number'] is not None for driver in available))
            self.assertTrue(all(driver['tyre_life'] is not None for driver in available))

    def test_existing_china_sessions_have_tyre_life(self):
        for code in ('R', 'Q'):
            path = existing_path(ROOT, 2026, 'Chinese Grand Prix', code)
            result = read_payload(path, (2026, 'Chinese Grand Prix', code))
            self.assertEqual(len(result[3]), 22)
            available = [driver for driver in result[3].values() if driver['available']]
            self.assertTrue(all(driver['lap_number'] is not None for driver in available))
            self.assertTrue(all(driver['tyre_life'] is not None for driver in available))

    def test_existing_japan_is_complete(self):
        for code in ('R', 'Q'):
            path = existing_path(ROOT, 2026, 'Japanese Grand Prix', code)
            result = read_payload(path, (2026, 'Japanese Grand Prix', code))
            self.assertEqual(len(result[3]), 22)
            available = [driver for driver in result[3].values() if driver['available']]
            self.assertTrue(all(driver['lap_number'] is not None for driver in available))
            self.assertTrue(all(driver['tyre_life'] is not None for driver in available))

    def test_existing_miami_is_complete(self):
        for code in ('R', 'Q'):
            path = existing_path(ROOT, 2026, 'Miami Grand Prix', code)
            result = read_payload(path, (2026, 'Miami Grand Prix', code))
            self.assertEqual(len(result[3]), 22)
            available = [driver for driver in result[3].values() if driver['available']]
            self.assertTrue(all(driver['lap_number'] is not None for driver in available))
            self.assertTrue(all(driver['tyre_life'] is not None for driver in available))

    def test_existing_canada_is_complete(self):
        for code in ('R', 'Q'):
            path = existing_path(ROOT, 2026, 'Canadian Grand Prix', code)
            result = read_payload(path, (2026, 'Canadian Grand Prix', code))
            self.assertEqual(len(result[3]), 22)
            available = [driver for driver in result[3].values() if driver['available']]
            self.assertTrue(all(driver['lap_number'] is not None for driver in available))
            self.assertTrue(all(driver['tyre_life'] is not None for driver in available))

    def test_existing_sprints_are_complete(self):
        for event in (
            'Chinese Grand Prix', 'Miami Grand Prix', 'Canadian Grand Prix'
        ):
            path = existing_path(ROOT, 2026, event, 'S')
            result = read_payload(path, (2026, event, 'S'))
            self.assertEqual(len(result[3]), 22)
            available = [driver for driver in result[3].values() if driver['available']]
            self.assertTrue(all(driver['lap_number'] is not None for driver in available))
            self.assertTrue(all(driver['tyre_life'] is not None for driver in available))

    def test_existing_monaco_is_complete(self):
        for code in ('R', 'Q'):
            path = existing_path(ROOT, 2026, 'Monaco Grand Prix', code)
            result = read_payload(path, (2026, 'Monaco Grand Prix', code))
            self.assertEqual(len(result[3]), 22)
            available = [driver for driver in result[3].values() if driver['available']]
            self.assertGreaterEqual(len(available), 20)
            self.assertTrue(all(driver['lap_number'] is not None for driver in available))
            self.assertTrue(all(driver['tyre_life'] is not None for driver in available))

    def test_invalid_drivers_safe(self):
        payload = json.loads((ROOT / '2026_australia_race.json').read_text())
        payload['drivers'].append(None)
        self.assertTrue(validate_payload(payload)[4])
        payload['drivers'] = payload['drivers'][:1]
        with self.assertRaises(ValueError):
            validate_payload(payload)

    def test_tyre_life_is_optional_but_validated(self):
        payload = json.loads((ROOT / '2026_australia_race.json').read_text())
        legacy = validate_payload(payload)[3]
        self.assertIsNone(next(iter(legacy.values()))['tyre_life'])
        payload['drivers'][0]['tyre_life'] = 3
        result = validate_payload(payload)[3]
        self.assertEqual(result[payload['drivers'][0]['code']]['tyre_life'], 3.0)
        payload['drivers'][0]['tyre_life'] = 0
        self.assertTrue(any('胎齡無效' in item for item in validate_payload(payload)[4]))

    def test_lap_number_is_optional_but_validated(self):
        payload = json.loads((ROOT / '2026_australia_race.json').read_text())
        legacy = validate_payload(payload)[3]
        self.assertIsNone(next(iter(legacy.values()))['lap_number'])
        payload['drivers'][0]['lap_number'] = 12
        result = validate_payload(payload)[3]
        self.assertEqual(result[payload['drivers'][0]['code']]['lap_number'], 12)
        payload['drivers'][0]['lap_number'] = 12.5
        self.assertTrue(any('最快圈圈次無效' in item for item in validate_payload(payload)[4]))

    def test_unavailable_driver_stays_in_roster(self):
        payload = json.loads((ROOT / '2026_australia_race.json').read_text())
        payload['drivers'].append({
            'code': 'DNS', 'name': 'No timed lap', 'team': 'Test',
            'available': False, 'reason': '沒有有效最快圈'
        })
        drivers = validate_payload(payload)[3]
        self.assertIn('DNS', drivers)
        self.assertFalse(drivers['DNS']['available'])
        self.assertIsNone(drivers['DNS']['telemetry'])

    def test_atomic_failure_preserves_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'file.json'
            atomic_json(path, {'old': True})
            with self.assertRaises(ValueError):
                atomic_json(path, {'broken': float('nan')})
            self.assertEqual(json.loads(path.read_text()), {'old': True})

    def test_compact_telemetry_preserves_endpoints(self):
        import pandas as pd
        frame = pd.DataFrame({'value': range(1000)})
        compact = compact_telemetry(frame, max_points=300)
        self.assertEqual(len(compact), 300)
        self.assertEqual(compact.iloc[0]['value'], 0)
        self.assertEqual(compact.iloc[-1]['value'], 999)

    def test_unfinished_session_not_exported(self):
        import pandas as pd
        fastf1 = Mock()
        fastf1.get_session.return_value.session_status = pd.DataFrame({'Status': ['Started', 'Finished']})
        with self.assertRaisesRegex(ValueError, 'Finalised'):
            export_session(fastf1, 2026, 'Test', 'Q')

    def test_export_resumes_and_does_not_fetch_future(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            event = {'event': 'Australian Grand Prix', 'sessions': {
                'R': {'start_utc': '2026-03-08T04:00:00Z'},
                'Q': {'start_utc': '2099-01-01T00:00:00Z'}}}
            atomic_json(root / 'data/schedule_2026.json', {'year': 2026, 'events': [event]})
            payload = json.loads((ROOT / '2026_australia_race.json').read_text())
            atomic_json(root / '2026_australia_race.json', payload)
            args = Namespace(year=2026, saved_schedule=True, event=None, sessions=['R', 'Q'], refresh=False)
            fake = Mock()
            self.assertEqual(run(args, fake, root), 0)
            fake.get_session.assert_not_called()
            report = json.loads((root / 'data/export_report_2026.json').read_text())
            self.assertEqual([s['status'] for s in report['sessions']], ['saved', 'future'])


if __name__ == '__main__':
    unittest.main()
