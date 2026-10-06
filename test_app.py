"""Offline Streamlit smoke tests. Run: python -m unittest test_app -v"""
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent


class AppTests(unittest.TestCase):
    def test_barcelona_sessions_stay_offline(self):
        with patch('fastf1.get_session', side_effect=AssertionError('Website must stay offline')):
            app = AppTest.from_file(str(ROOT / 'demo.py'), default_timeout=30).run()
            app.selectbox[0].set_value(6).run()
            self.assertFalse(app.exception)
            self.assertFalse(app.error)
            self.assertEqual(len(app.selectbox[2].options), 22)
            app.selectbox[2].set_value('BEA').run()
            self.assertFalse(app.exception)
            self.assertFalse(app.error)
            self.assertTrue(any('最快圈胎齡：未提供' in m.value for m in app.markdown))
            app.selectbox[1].set_value('Q').run()
            self.assertFalse(app.exception)
            self.assertFalse(app.error)
            self.assertEqual(len(app.selectbox[2].options), 22)
            self.assertTrue(any('最快圈圈次：第' in m.value for m in app.markdown))

    def test_austria_sessions_stay_offline(self):
        with patch('fastf1.get_session', side_effect=AssertionError('Website must stay offline')):
            app = AppTest.from_file(str(ROOT / 'demo.py'), default_timeout=30).run()
            app.selectbox[0].set_value(7).run()
            app.selectbox[2].set_value('BOT').run()
            for code in ('R', 'Q'):
                with self.subTest(session=code):
                    app.selectbox[1].set_value(code).run()
                    self.assertFalse(app.exception)
                    self.assertFalse(app.error)
                    self.assertEqual(len(app.selectbox[2].options), 22)
                    self.assertTrue(any('最快圈圈次：第' in m.value for m in app.markdown))
                    self.assertFalse(any('最快圈胎齡：未提供' in m.value for m in app.markdown))

    def test_sprint_session_available(self):
        app = AppTest.from_file(str(ROOT / 'demo.py'), default_timeout=30).run()
        app.selectbox[0].set_value(1).run()
        self.assertFalse(app.exception)
        self.assertIn('衝刺賽 (Sprint)', app.selectbox[1].options)
        app.selectbox[1].set_value('S').run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.selectbox), 4)
        self.assertEqual(len(app.selectbox[2].options), 22)

    def test_available_missing_and_future(self):
        app = AppTest.from_file(str(ROOT / 'demo.py'), default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.selectbox), 4)
        self.assertEqual(len(app.selectbox[2].options), 22)
        self.assertTrue(any('最快圈圈次：第' in item.value for item in app.markdown))
        unavailable_app = AppTest.from_file(str(ROOT / 'demo.py'), default_timeout=30).run()
        unavailable_app.selectbox[2].set_value('HUL').run()
        self.assertFalse(unavailable_app.exception)
        self.assertTrue(any('無法繪製' in i.value for i in unavailable_app.info))
        with patch('race_data.session_state', return_value=('future', '尚未開賽')):
            app.selectbox[0].set_value(22).run()
            self.assertFalse(app.exception)
            self.assertTrue(any('尚未開賽' in i.value for i in app.info))
            self.assertEqual(len(app.selectbox), 2)
        missing_app = AppTest.from_file(str(ROOT / 'demo.py'), default_timeout=30)
        with patch('race_data.Path.is_file', return_value=False), patch(
                'race_data.session_state', return_value=('missing', '資料尚未收錄')):
            missing_app.run()
            missing_app.selectbox[0].set_value(1).run()
            self.assertFalse(missing_app.exception)
            self.assertTrue(any('尚未收錄' in i.value for i in missing_app.info))


if __name__ == '__main__':
    unittest.main()
