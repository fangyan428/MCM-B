import json
from pathlib import Path
import unittest
from question3.cases import clustered_case,random_case,boundary_case
from question3.interface import Client
from question3.simulator import Simulator
from question3.strategy import run


def cfg(name):return json.loads(Path('question3/configs/round4_adapt',name+'.json').read_text())

class OriginRingTests(unittest.TestCase):
    def test_cluster_and_outer_ring_fallback(self):
        for case in [clustered_case(),boundary_case()]:
            reference=run(Client(Simulator(case),'SELF'),cfg('ABS'))
            events=[];e=Simulator(case);actual=run(Client(e,'SELF'),cfg('ABSR1125E'),events.append)
            self.assertEqual(actual['metrics'],reference['metrics'])
            self.assertEqual(actual['status'],'complete');self.assertTrue(any(x['type']=='search_ring_switch' for x in events))
            self.assertEqual(actual['station_positions'][1],[1500.,0.] if isinstance(actual['station_positions'][1],list) else (1500.,0.))
    def test_positive_origin_keeps_compact_ring(self):
        case=random_case(0);ref=run(Client(Simulator(case),'SELF'),cfg('ABSR1125'))
        es=[];r=run(Client(Simulator(case),'SELF'),cfg('ABSR1125E'),es.append)
        self.assertEqual(r['metrics'],ref['metrics']);self.assertFalse(any(x['type']=='search_ring_switch' for x in es))
    def test_fallback_still_needs_coverage_certificate(self):
        c=cfg('ABSR1125E');c['empty_origin_radius_m']=1100
        client=Client(Simulator(random_case(0)),'SELF')
        with self.assertRaises(ValueError):run(client,c)
        self.assertFalse(client.entered)
