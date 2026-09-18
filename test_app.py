"""Offline Streamlit smoke tests. Run: python -m unittest test_app -v"""
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent


class AppTests(unittest.TestCase):
    def test_available_missing_and_future(self):
        app = AppTest.from_file(str(ROOT / 'demo.py'), default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.selectbox), 4)
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
