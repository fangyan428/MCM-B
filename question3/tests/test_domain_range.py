"""Continuous-certificate boundary checks and public-region invariants."""
import json
import math
from pathlib import Path
import unittest
import numpy as np
from question2.strategy import candidate,to_world
from question3.domain_range import range_upper,certified,proxy
from question3.modules import choose_second,design_catalog
from question3.cases import random_case,late_source_case,boundary_case
from question3.interface import Client
from question3.simulator import Simulator
from question3.strategy import run


def config():return json.loads(Path('question3/configs/round18_dev/DOMAIN.json').read_text())


class DomainRangeTests(unittest.TestCase):
    def test_range_bound_encloses_dense_boundary_rays_and_wraparound(self):
        for first in [(0,0),(1125,0),(-1125,1e-8),(0,1800),(1800-1e-8,0)]:
            for bearing in np.linspace(-361,361,39):
                upper=range_upper(first,bearing,1.005)
                for angle in np.radians(bearing+np.linspace(-1.005,1.005,101)):
                    projection=first[0]*math.cos(angle)+first[1]*math.sin(angle)
                    bound=min(1500,-projection+math.sqrt(max(0,projection**2+1800**2-math.hypot(*first)**2)))
                    self.assertGreaterEqual(upper+1e-8,bound)
        self.assertEqual(range_upper((1801,0),0,1.005),1500)
        self.assertEqual(range_upper((0,0),0,1.005),1500)
        self.assertLess(range_upper((1125,0),0,1.005),677)

    def test_certified_sector_reception_and_angle_dense_extremes(self):
        accepted=0
        for upper in [6,20,100,675,999,1000,1001,1200,1500]:
            offsets=[tuple(row['offset']) for row in design_catalog()]
            offsets += [(a*upper/1500,b*upper/1500) for a,b in offsets]
            for q in offsets:
                if not certified(q,upper,1.005,20):continue
                accepted+=1
                r,t=np.meshgrid(np.linspace(5,upper,61),np.radians(np.linspace(-1.005,1.005,31)),indexing='ij')
                g=np.stack([r*np.cos(t),r*np.sin(t)],axis=-1);v=g-q;distance=np.linalg.norm(v,axis=-1)
                self.assertTrue(np.all(distance<=np.maximum(1000,r)+1e-7))
                sine=np.abs(g[...,0]*v[...,1]-g[...,1]*v[...,0])/(r*distance)
                self.assertGreaterEqual(float(sine.min()),math.sin(math.radians(20))-1e-9)
                self.assertGreater(float(distance.min()),5)
        self.assertGreater(accepted,100)

    def test_old_invalid_offset_can_be_valid_on_domain_but_not_assumed_globally(self):
        q=(300.,250.)
        self.assertFalse(candidate(q,20,1.005));self.assertTrue(certified(q,676,1.005,20))
        self.assertFalse(certified(q,1500,1.005,20))
        for q in [(0,0),(-200,300),(500,0),(5000,5000),(float('nan'),400)]:
            self.assertFalse(certified(q,676,1.005,20))

    def test_full_range_fallback_exact_and_current_opportunity(self):
        c=config();old={**c,'second_range_prior':'off'}
        self.assertEqual(choose_second((0,0),45,(22,33),c),choose_second((0,0),45,(22,33),old))
        first=(1125.,0.);current=tuple(to_world((300,250),first,0))
        q,s=choose_second(first,0,current,c)
        self.assertEqual(q,current);self.assertEqual(s['mode'],'domain_current')
        self.assertGreaterEqual(s['source_range_upper_m'],675)

    def test_whole_workflow_still_clears_late_and_boundary_sources(self):
        for case in [random_case(0),late_source_case(),boundary_case()]:
            env=Simulator(case);events=[];r=run(Client(env,'SELF'),config(),events.append)
            self.assertEqual(r['status'],'complete');self.assertFalse(env.evaluation()['remaining_channels'])
            self.assertLessEqual(sum(e['type']=='schedule' for e in events),23)
            if case['id']=='late_channel20_after_ten':self.assertIn(20,r['cleared_channels'])

    def test_contradictory_domain_second_reading_never_completes(self):
        active=False;hit=False
        class BadClient(Client):
            def measure(self,p,c,phase='measure'):
                nonlocal hit
                r=super().measure(p,c,phase)
                if active and phase=='localization':hit=True;return {**r,'measure_result':'no_signal'}
                return r
        def event(e):
            nonlocal active
            if e['type']=='second_point_after_schedule':active=e['selection_mode'].startswith('domain_')
        r=run(BadClient(Simulator(random_case(0)),'SELF'),config(),event)
        self.assertTrue(hit);self.assertEqual(r['status'],'incomplete');self.assertFalse(r['exit_confirmed'])

    def test_invalid_configuration_before_enter(self):
        for change in [dict(second_range_prior='bad'),dict(opportunity_timing='before_schedule'),dict(modules={})]:
            client=Client(Simulator(random_case(0)),'SELF')
            with self.assertRaises(ValueError):run(client,{**config(),**change})
            self.assertFalse(client.entered)
