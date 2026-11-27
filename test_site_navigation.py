"""Navigation must preserve comparisons and restore a shared URL offline."""
import unittest
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from race_data import read_catalogue
from site_navigation import decode_link,BASE_URL

ROOT=Path(__file__).resolve().parent


class SiteNavigationTests(unittest.TestCase):
    def app(self,query=None):
        app=AppTest.from_file(str(ROOT/'demo.py'),default_timeout=30)
        if query:
            app.query_params.update(query)
        return app

    def test_shared_analysis_restores_event_session_drivers_and_tab(self):
        query=dict(site_view='數據分析',year='2026',event='las_vegas_grand_prix',session='R',a='NOR',b='VER',analysis_tab='整場節奏與輪胎')
        with patch('fastf1.get_session',side_effect=AssertionError('offline')):
            app=self.app(query).run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['page'],'analysis')
            self.assertEqual(app.selectbox(key='event_index').value,20)
            self.assertEqual(app.selectbox(key='analysis_a').value,'NOR')
            self.assertEqual(app.selectbox(key='analysis_b').value,'VER')
            self.assertEqual(app.session_state['analysis_tab'],'整場節奏與輪胎')
            url=next(x.value for x in app.code if x.value.startswith(BASE_URL))
            shared={k:v[-1] for k,v in parse_qs(urlparse(url).query).items()}
            fresh=self.app(shared).run()
            self.assertFalse(fresh.exception)
            self.assertEqual(fresh.selectbox(key='analysis_a').value,'NOR')
            self.assertEqual(fresh.selectbox(key='analysis_b').value,'VER')
            self.assertEqual(fresh.session_state['analysis_tab'],'整場節奏與輪胎')

    def test_navigation_roundtrip_retains_selection(self):
        app=self.app().run()
        app.selectbox(key='home_event').set_value(20).run()
        app.selectbox(key='case_b').set_value('NOR').run()
        app.radio(key='site_view').set_value('賽程與賽道').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['page'],'calendar')
        self.assertEqual(app.selectbox(key='home_event').value,20)
        app.button(key='calendar_analysis').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key='analysis_b').value,'NOR')
        app.radio(key='site_view').set_value('車迷入門').run()
        self.assertFalse(app.exception)
        self.assertTrue(any('第一次看 F1' in h.value for h in app.header))
        app.radio(key='site_view').set_value('數據分析').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key='event_index').value,20)
        self.assertEqual(app.selectbox(key='analysis_b').value,'NOR')

    def test_control_changes_update_share_without_reapplying_old_url(self):
        app=self.app(dict(site_view='數據分析',event='las_vegas_grand_prix',a='ANT',b='LEC')).run()
        app.selectbox(key='analysis_b').set_value('NOR').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.query_params['b'],'NOR')
        app.selectbox(key='event_index').set_value(17).run()
        self.assertEqual(app.selectbox(key='event_index').value,17)
        self.assertEqual(app.query_params['event'],'united_states_grand_prix')

    def test_invalid_link_is_bounded_and_explained(self):
        catalogue=read_catalogue(ROOT/'data/schedule_2026.json')
        result,notices=decode_link(dict(site_view='../secret',year='2027',event='../../etc/passwd',session='Z',a='<script>',analysis_tab='bad'),catalogue)
        self.assertEqual(result['view'],'觀賽首頁')
        self.assertEqual(result['index'],17)
        self.assertEqual(result['code'],'R')
        self.assertIsNone(result['a'])
        self.assertGreaterEqual(len(notices),4)
        app=self.app(dict(site_view='數據分析',event='las_vegas_grand_prix',a='ZZZ',b='LEC')).run()
        self.assertFalse(app.exception)
        self.assertTrue(any('不在本場名單' in i.value for i in app.info))
        self.assertNotEqual(app.selectbox(key='analysis_a').value,'ZZZ')

    def test_calendar_without_data_keeps_learning_path(self):
        app=self.app(dict(site_view='賽程與賽道',event='qatar_grand_prix')).run()
        self.assertFalse(app.exception)
        self.assertTrue(app.button(key='calendar_analysis').disabled)
        self.assertTrue(any('尚無離線' in i.value for i in app.info))
        app.radio(key='site_view').set_value('車迷入門').run()
        self.assertFalse(app.exception)

    def test_reading_detour_preserves_analysis_context(self):
        app=self.app(dict(site_view='數據分析',event='las_vegas_grand_prix',a='NOR',b='VER',analysis_tab='單圈資料',large='1')).run()
        app.radio(key='site_view').set_value('車迷入門').run()
        # Two learning reruns exercise Streamlit's cleanup of hidden widgets.
        app.text_input(key='glossary_search').set_value('Brake').run()
        app.radio(key='site_view').set_value('數據分析').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['analysis_tab'],'單圈資料')
        self.assertTrue(app.checkbox(key='analysis_large').value)
        self.assertEqual(app.selectbox(key='analysis_a').value,'NOR')
        self.assertEqual(app.selectbox(key='analysis_b').value,'VER')

    def test_calendar_distinguishes_fastest_and_lap_coverage(self):
        app=self.app(dict(site_view='賽程與賽道',event='las_vegas_grand_prix',session='R')).run()
        self.assertFalse(app.exception)
        self.assertTrue(any('拉斯維加斯站 · 已存 2/2 場' in option for option in app.selectbox(key='home_event').options))
        self.assertTrue(any('整場逐圈：已收錄' in x.value for x in app.markdown))
        app.selectbox(key='home_session').set_value('Q').run()
        self.assertTrue(any('不適用於排位賽' in x.value for x in app.markdown))
        app.selectbox(key='home_event').set_value(21).run()
        self.assertTrue(app.button(key='calendar_analysis').disabled)
        self.assertTrue(any('最快圈比對：尚未收錄' in x.value for x in app.markdown))

    def test_deploy_replaces_retained_homepage_callback(self):
        import homepage
        with patch.object(homepage,'choose_home_entry',side_effect=AssertionError('stale UI callback')), patch.object(homepage,'_fp_ui_release','older',create=True):
            app=self.app().run()
            app.button(key='home_beginner').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['site_view'],'車迷入門')

if __name__=='__main__':
    unittest.main()
