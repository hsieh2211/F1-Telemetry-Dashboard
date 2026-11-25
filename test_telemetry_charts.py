"""Alignment probe keeps discrete brakes and does not mutate raw exports."""
import unittest
import numpy as np
import pandas as pd
from telemetry_charts import aligned_samples, telemetry_chart


class TelemetryChartTests(unittest.TestCase):
    def sample(self):
        a = pd.DataFrame(dict(Distance=[0.,25.,50.,100.],Speed=[100.,125.,150.,200.],Throttle=[0.,25.,50.,100.],Brake=[1.,1.,0.,0.]))
        b = pd.DataFrame(dict(Distance=[0.,100.,200.],Speed=[100.,150.,200.],Throttle=[0.,50.,100.],Brake=[1.,0.,1.]))
        return a,b

    def test_probe_interpolates_continuous_values_but_preserves_discrete_brakes(self):
        a,b=self.sample()
        saved_a,saved_b=a.copy(),b.copy()
        result=aligned_samples(a,b,np.array([0.,.1,.2,.3]))
        self.assertEqual(result.b_Speed.tolist(),[100.,125.,150.,200.])
        self.assertEqual(result.b_Brake.tolist(),[1.,1.,0.,1.])
        self.assertEqual(result.delta.tolist(),[0.,.1,.2,.3])
        pd.testing.assert_frame_equal(a,saved_a)
        pd.testing.assert_frame_equal(b,saved_b)

    def test_full_view_has_one_shared_click_probe_and_four_signals(self):
        a,b=self.sample()
        spec=telemetry_chart(a,b,np.zeros(4),'AAA','BBB','完整訊號').to_dict()
        self.assertEqual(len(spec['vconcat']),4)
        self.assertEqual(len(spec['params']),1)
        self.assertIn('click',spec['params'][0]['select']['on'])
        self.assertEqual(spec['resolve']['scale']['x'],'shared')
        self.assertIn('對齊估計',str(spec))
        self.assertEqual(len(telemetry_chart(a,b,np.zeros(4),'AAA','BBB').to_dict()['vconcat']),2)

if __name__=='__main__':
    unittest.main()
