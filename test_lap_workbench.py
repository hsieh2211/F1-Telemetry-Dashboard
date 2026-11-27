import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from race_lap_workbench import bounded_lap,selected_rows,linked_chart,accept_chart_lap
from race_pace import export_laps,validate_laps,pace_rows
from race_pace_ui import TYRES
from test_race_pace import fixture,IDENTITY

ROOT=Path(__file__).resolve().parent


class LapWorkbenchTests(unittest.TestCase):
    def frame(self):
        return pace_rows(validate_laps(export_laps(fixture(),*IDENTITY,'test'),IDENTITY)[1])

    def test_missing_lap_is_not_replaced(self):
        frame=self.frame()
        frame=frame[~((frame.driver=='AAA')&(frame.lap==4))]
        rows=selected_rows(frame,['AAA','BBB'],4)
        self.assertIsNone(rows[0][1])
        self.assertEqual(rows[1][1]['pit_in_seconds'],390)
        self.assertIn('進出站圈',rows[1][1]['excluded_reason'])

    def test_linked_chart_preserves_exclusions_and_single_focus(self):
        specs=[c.to_dict() for c in linked_chart(self.frame(),['AAA','BBB'],{'AAA':'red','BBB':'blue'},TYRES,1,8,4)]
        self.assertEqual(len(specs),3)
        for spec in specs:
            self.assertEqual(len(spec['params']),1)
            self.assertEqual(spec['params'][0]['select']['fields'],['lap'])
            self.assertEqual(spec['autosize']['type'],'fit-x')
            self.assertEqual(spec['layer'][0]['encoding']['x']['scale']['domain'],[.5,8.5])
            self.assertFalse(spec['layer'][0]['encoding']['x']['scale']['nice'])
        records=[r for spec in specs for rows in spec['datasets'].values() for r in rows]
        self.assertTrue(any(r.get('focus')==4 for r in records))
        self.assertTrue(any('進出站圈' in r.get('excluded_reason','') for r in records))

    def test_event_is_bounded_to_current_range(self):
        state={'chart':{'selection':{'lap_pick':[{'lap':6}]}}}
        with patch('race_lap_workbench.st.session_state',state):
            accept_chart_lap('chart','focus',3,8)
            self.assertEqual(state['focus'],6)
            accept_chart_lap('chart','focus',7,8)
            self.assertEqual(state['focus'],7)
        self.assertEqual(bounded_lap(None,3,8),3)
        self.assertEqual(bounded_lap(4.5,3,8),3)

    def test_real_race_focus_and_range_clamp_stay_offline(self):
        with patch('fastf1.get_session',side_effect=AssertionError('offline')):
            app=AppTest.from_file(str(ROOT/'demo.py'),default_timeout=30)
            app.query_params.update(site_view='數據分析',event='las_vegas_grand_prix',a='ANT',b='LEC',analysis_tab='整場節奏與輪胎')
            app.run()
            focus='pace_focus_2026_Las Vegas Grand Prix_R'
            app.selectbox(key=focus).set_value(14).run()
            self.assertFalse(app.exception)
            self.assertTrue(any('圈速：97.886 秒'==m.value for m in app.markdown))
            self.assertTrue(any('圈速：98.401 秒'==m.value for m in app.markdown))
            app.slider(key='pace_range_2026_Las Vegas Grand Prix_R').set_value((20,30)).run()
            self.assertFalse(app.exception)
            self.assertEqual(app.selectbox(key=focus).value,20)
            self.assertTrue(any('第 20 圈 · 同步查看' in m.value for m in app.markdown))

    def test_native_tab_change_keeps_programmatic_analysis_destination(self):
        app=AppTest.from_file(str(ROOT/'demo.py'),default_timeout=30).run()
        app.button(key='home_analysis').click().run()
        self.assertEqual(app.session_state['page'],'analysis')
        # The native bound tab can omit the default navigation parameter.
        app.query_params['analysis_tab']='整場節奏與輪胎'
        app.session_state['analysis_tab']='整場節奏與輪胎'
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['page'],'analysis')

if __name__=='__main__':
    unittest.main()
