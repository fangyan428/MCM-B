import json
import math
from pathlib import Path
import unittest
import numpy as np
from question2.strategy import candidate,to_world
from question3.current_point import current_proxy,local_offset
from question3.modules import design_catalog,choose_second
from question3.cases import random_case,late_source_case
from question3.interface import Client
from question3.simulator import Simulator
from question3.strategy import run


def cfg(n='J'):return json.loads(Path('question3/configs/round8_dev',n+'.json').read_text())


class CurrentPointTests(unittest.TestCase):
    def test_rotation_and_exact_current_position(self):
        first=(234.,-567.);bearing=37.;current=tuple(to_world((500,500),first,bearing))
        np.testing.assert_allclose(local_offset(first,bearing,current),(500,500),atol=1e-10,rtol=0)
        q,s=choose_second(first,bearing,current,cfg('Z'))
        self.assertEqual(q,current);self.assertEqual(s['mode'],'opportunistic_current')
        self.assertTrue(candidate(s['offset'],20,1.005))

    def test_same_proxy_as_catalog_and_invalid_points_excluded(self):
        for row in design_catalog():
            p=current_proxy(row['offset'],1.005,20)
            self.assertAlmostEqual(p['sampled_worst_diameter'],row['sampled_worst_diameter'],places=7)
            self.assertEqual(p['proxy_cells'],row['proxy_cells'])
            self.assertAlmostEqual(p['continuation_proxy_s'],row['continuation_proxy_s'],places=7)
        for point in [(0,0),(700,0),(-500,500),(1200,1200)]:
            self.assertIsNone(current_proxy(point,1.005,20))
            base=choose_second((0,0),0,point,cfg('REF'))
            self.assertEqual(choose_second((0,0),0,point,cfg('J')),base)

    def test_cheaper_gate_rejects_costly_admissible_current(self):
        # Fixed development geometry: test both possible branches without fitting a threshold.
        decisions=[]
        for a in [200,400,600,800]:
            for b in [300,500,700]:
                if not candidate((a,b),20,1.005):continue
                q,s=choose_second((0,0),0,(a,b),cfg('J'))
                old_q,old=choose_second((0,0),0,(a,b),cfg('REF'))
                self.assertLessEqual(s['score_s'],old['score_s']+1e-8)
                decisions.append(s['mode'])
        self.assertIn('opportunistic_current',decisions);self.assertIn('cost_proxy',decisions)

    def test_complete_flow_no_move_and_late_source(self):
        for case in [random_case(0),late_source_case()]:
            requests=[];events=[];env=Simulator(case)
            r=run(Client(env,'SELF',requests.append),cfg('J'),events.append)
            self.assertEqual(r['status'],'complete');self.assertFalse(env.evaluation()['remaining_channels'])
            selected=[e for e in events if e['type']=='localization' and e['selection']['mode']=='opportunistic_current']
            if case['id']=='dev_0_spatial_hash':self.assertTrue(selected)
            position=(0.,0.);moves={}
            for e in requests:
                if e['type']=='request' and e['path'] in ('/measure','/clear'):
                    p=e['payload']['position'];q=(p['x'],p['y'])
                    if e['path']=='/measure' and e['phase']=='localization':moves[e['payload']['channel']]=math.dist(position,q)
                    position=q
            for e in selected:self.assertEqual(moves[e['channel']],0)
            if case['id']=='late_channel20_after_ten':self.assertIn(20,r['cleared_channels'])

    def test_contradictory_current_reading_is_incomplete(self):
        env=Simulator(random_case(0));hit=False
        class BadClient(Client):
            def measure(self,p,c,phase='measure'):
                nonlocal hit
                no_move=tuple(p)==tuple(self.position)
                r=super().measure(p,c,phase)
                if no_move and phase=='localization':
                    hit=True;return {**r,'measure_result':'no_signal'}
                return r
        r=run(BadClient(env,'SELF'),cfg('J'))
        self.assertTrue(hit);self.assertEqual(r['status'],'incomplete');self.assertFalse(r['exit_confirmed'])

    def test_invalid_configuration_before_enter(self):
        for bad in [{**cfg(),'second_point_opportunity':'unknown'},
                    {**cfg(),'modules':{**cfg()['modules'],'A':False}}]:
            client=Client(Simulator(random_case(0)),'SELF')
            with self.assertRaises(ValueError):run(client,bad)
            self.assertFalse(client.entered)
