"""Offline Streamlit smoke tests. Run: python -m unittest test_app -v"""
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent


def analysis_app():
    app = AppTest.from_file(str(ROOT / 'demo.py'), default_timeout=30)
    app.session_state['page'] = 'analysis'
    return app


class AppTests(unittest.TestCase):
    def test_same_driver_is_not_presented_as_comparison(self):
        app = analysis_app().run()
        app.selectbox(key='analysis_b').set_value(app.selectbox(key='analysis_a').value).run()
        self.assertFalse(app.exception)
        self.assertTrue(any('兩位不同車手' in x.value for x in app.info))
        self.assertFalse(app.metric)

    def test_home_pair_handoff_and_return_preserve_selection(self):
        with patch('fastf1.get_session', side_effect=AssertionError('offline')):
            app = AppTest.from_file(str(ROOT / 'demo.py'), default_timeout=30).run()
            app.selectbox(key='case_a').set_value('NOR').run()
            app.selectbox(key='case_b').set_value('PIA').run()
            app.button(key='home_analysis').click().run()
            self.assertEqual(app.selectbox(key='analysis_a').value, 'NOR')
            self.assertEqual(app.selectbox(key='analysis_b').value, 'PIA')
            self.assertTrue(any('諾里斯' in x for x in app.selectbox(key='analysis_a').options))
            app.selectbox(key='event_index').set_value(19).run()
            app.selectbox(key='session_code').set_value('Q').run()
            app.button[0].click().run()
            self.assertEqual(app.selectbox(key='home_event').value, 19)
            self.assertEqual(app.selectbox(key='home_session').value, 'Q')
            self.assertEqual(app.selectbox(key='case_a').value, 'NOR')
            self.assertEqual(app.selectbox(key='case_b').value, 'PIA')
            self.assertFalse(app.exception)

    def test_barcelona_sessions_stay_offline(self):
        with patch('fastf1.get_session', side_effect=AssertionError('Website must stay offline')):
            app = analysis_app().run()
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
            app = analysis_app().run()
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

    def test_british_sessions_stay_offline(self):
        with patch('fastf1.get_session', side_effect=AssertionError('Website must stay offline')):
            app = analysis_app().run()
            app.selectbox[0].set_value(8).run()
            app.selectbox[2].set_value('VER').run()
            for code in ('R', 'Q'):
                with self.subTest(session=code):
                    app.selectbox[1].set_value(code).run()
                    self.assertFalse(app.exception)
                    self.assertFalse(app.error)
                    self.assertEqual(len(app.selectbox[2].options), 22)
                    self.assertTrue(any('最快圈圈次：第' in m.value for m in app.markdown))
                    self.assertFalse(any('最快圈胎齡：未提供' in m.value for m in app.markdown))

    def test_belgian_sessions_stay_offline_and_handle_no_lap(self):
        with patch('fastf1.get_session', side_effect=AssertionError('Website must stay offline')):
            app = analysis_app().run()
            app.selectbox[0].set_value(9).run()
            # Preserve the selected driver across events, including a no-lap driver.
            self.assertTrue(any('沒有有效最快圈' in i.value for i in app.info))
            app.selectbox(key='analysis_a').set_value('ANT').run()
            app.selectbox(key='analysis_b').set_value('LEC').run()
            self.assertFalse(app.exception)
            self.assertFalse(app.error)
            self.assertEqual(len(app.selectbox[2].options), 22)
            self.assertTrue(any('最快圈圈次：第' in m.value for m in app.markdown))
            app.selectbox[2].set_value('RUS').run()
            self.assertFalse(app.exception)
            self.assertFalse(app.error)
            self.assertTrue(any('沒有有效最快圈' in i.value for i in app.info))
            app.selectbox[1].set_value('Q').run()
            self.assertFalse(app.exception)
            self.assertFalse(app.error)
            self.assertEqual(len(app.selectbox[2].options), 22)
            self.assertTrue(any('最快圈圈次：第' in m.value for m in app.markdown))
            self.assertFalse(any('最快圈胎齡：未提供' in m.value for m in app.markdown))

    def test_sprint_session_available(self):
        app = analysis_app().run()
        app.selectbox[0].set_value(1).run()
        self.assertFalse(app.exception)
        self.assertIn('衝刺賽 (Sprint)', app.selectbox[1].options)
        app.selectbox[1].set_value('S').run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.selectbox), 4)
        self.assertEqual(len(app.selectbox[2].options), 22)

    def test_available_missing_and_future(self):
        app = analysis_app().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.selectbox), 4)
        self.assertEqual(len(app.selectbox[2].options), 22)
        self.assertTrue(any('最快圈圈次：第' in item.value for item in app.markdown))
        unavailable_app = analysis_app().run()
        unavailable_app.selectbox[2].set_value('HUL').run()
        self.assertFalse(unavailable_app.exception)
        self.assertTrue(any('無法繪製' in i.value for i in unavailable_app.info))
        with patch('race_data.session_state', return_value=('future', '尚未開賽')):
            app.selectbox[0].set_value(22).run()
            self.assertFalse(app.exception)
            self.assertTrue(any('尚未開賽' in i.value for i in app.info))
            self.assertEqual(len(app.selectbox), 2)
        missing_app = analysis_app()
        with patch('race_data.existing_path', return_value=ROOT / 'not-exported-test.json'), patch(
                'race_data.session_state', return_value=('missing', '資料尚未收錄')):
            missing_app.run()
            missing_app.selectbox[0].set_value(1).run()
            self.assertFalse(missing_app.exception)
            self.assertTrue(any('尚未收錄' in i.value for i in missing_app.info))


if __name__ == '__main__':
    unittest.main()
