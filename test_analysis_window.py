"""Windowing must preserve whole-lap timing and reset when context changes."""
import unittest
import types
from unittest.mock import patch
import numpy as np
from telemetry_charts import aligned_samples, telemetry_chart
from analysis_window import preset_window, window_observation
import test_telemetry_charts as chart_tests
import test_analysis_design as design_tests


class AnalysisWindowTests(unittest.TestCase):
    def test_window_retains_cumulative_delta_and_exact_domain(self):
        a,b=chart_tests.TelemetryChartTests().sample()
        delta=np.array([0.,.1,.2,.3])
        frame=aligned_samples(a,b,delta)
        observation=window_observation(frame,25,50,'AAA','BBB')
        self.assertAlmostEqual(observation['start'],.1)
        self.assertAlmostEqual(observation['end'],.2)
        self.assertAlmostEqual(observation['movement'],.1)
        self.assertIn('向 AAA',observation['text'])
        self.assertIsNone(window_observation(frame,30,30,'AAA','BBB'))
        self.assertIsNone(window_observation(frame,200,300,'AAA','BBB'))
        spec=telemetry_chart(a,b,delta,'AAA','BBB',window=(25,50)).to_dict()
        self.assertEqual(spec['vconcat'][0]['layer'][0]['encoding']['x']['scale']['domain'],[25,50])
        source=next(iter(spec['datasets'].values()))
        self.assertTrue(any(r.get('delta')==.3 for r in source))
        self.assertEqual(spec['config']['axis']['labelColor'],'#c4d1e2')
        with self.assertRaises(ValueError):
            telemetry_chart(a,b,delta,'AAA','BBB',window=(25,25))

    def test_presets_cover_full_distance_without_gaps(self):
        self.assertEqual(preset_window(101), (0,101))
        parts=[preset_window(101,i) for i in range(3)]
        self.assertEqual(parts,[(0,33),(33,67),(67,101)])

    def test_analysis_ignores_a_preloaded_legacy_chart_module(self):
        legacy=types.ModuleType('telemetry_charts')
        def old_chart(a,b,delta,a_code,b_code,view):
            raise AssertionError('legacy chart must not be used')
        legacy.telemetry_chart=old_chart
        legacy.aligned_samples=lambda *args: None
        with patch.dict('sys.modules', {'telemetry_charts': legacy}):
            app=design_tests.AnalysisDesignTests().app().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertEqual(app.slider(key='telemetry_window').value[0],0)

    def test_range_reset_presets_and_driver_change(self):
        app=design_tests.AnalysisDesignTests().app().run()
        self.assertFalse(app.exception)
        maximum=app.slider(key='telemetry_window').max
        app.slider(key='telemetry_window').set_value((1000,2000)).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.slider(key='telemetry_window').value,(1000,2000))
        app.button(key='reset_distance').click().run()
        self.assertEqual(app.slider(key='telemetry_window').value,(0,maximum))
        app.button(key='window_part_1').click().run()
        self.assertEqual(app.slider(key='telemetry_window').value,preset_window(maximum,1))
        app.selectbox(key='analysis_b').set_value('NOR').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.slider(key='telemetry_window').value,(0,maximum))
        app.checkbox(key='analysis_large').check().run()
        self.assertFalse(app.exception)
        app.slider(key='telemetry_window').set_value((2000,2000)).run()
        self.assertTrue(any('拉開距離' in i.value for i in app.info))

if __name__=='__main__':
    unittest.main()
