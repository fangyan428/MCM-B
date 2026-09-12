import copy
import math
import unittest
import numpy as np
from question3.interface import Client
from question4.simulator import Simulator
from question4.strategy import run
from question4.geometry import first_region, bearing_clip, optical_cover, mesh
from question4.cases import make_case
from question4.audit import audit

class ContractTests(unittest.TestCase):
    def test_directional_backside_near_and_optical(self):
        case=dict(sources=[dict(channel=1,x=0.,y=0.,radius=1000.,direction_deg=0.)])
        c=Client(Simulator(case),'SELF');c.enter()
        self.assertEqual(c.measure((-4,0),1)['measure_result'],'no_signal')
        self.assertEqual(c.measure((4,0),1)['measure_result'],'near')
        self.assertEqual(c.measure((0,1000),1)['measure_result'],'direction')
        self.assertEqual(c.measure((1001,0),1)['measure_result'],'no_signal')
        self.assertEqual(c.clear((-20,0),1)['clear_result'],'success')
        self.assertEqual(c.clear((-20,0),1)['clear_result'],'no_target_in_range')

    def test_clear_does_not_switch(self):
        case=make_case(42);c=Client(Simulator(case),'SELF');c.enter()
        c.measure((0,0),2);c.clear((0,0),3);self.assertEqual(c.channel,2)
        before=c.virtual;c.measure((0,0),2);self.assertAlmostEqual(c.virtual-before,5)

    def test_fixed_location_fixed_error_and_idempotent(self):
        case=dict(seed=7,sources=[dict(channel=1,x=500.,y=0.,radius=1000.,direction_deg=180.)])
        env=Simulator(case);c=Client(env,'SELF');c.enter()
        a=c.measure((0,0),1);b=c.measure((0,0),1)
        self.assertEqual(a['svd_deg'],b['svd_deg'])
        payload=dict(arena_id='default',robot_id='SELF',request_id='retry',position=dict(x=1,y=0),channel=1)
        r=env.request('/measure',payload);t=env.evaluation()['virtual_time_s']
        self.assertEqual(env.request('/measure',payload),r)
        self.assertEqual(env.evaluation()['virtual_time_s'],t)

    def test_sector_and_optical_certificate_error_extremes(self):
        for angle in (0,90,179.99,359.99):
            for error in (-1.005,1.005):
                for distance in (6.,500.,1500.):
                    p=np.array([0.,0.]);a=math.radians(angle+error)
                    g=distance*np.array([math.cos(a),math.sin(a)])
                    poly=first_region(p,angle)
                    # The optical grid must cover every legal true position in this fixture.
                    points,r=optical_cover(poly,angle,p)
                    self.assertLess(r,20)
                    self.assertLessEqual(min(math.dist(g,q) for q in points),20)

    def test_grid_detection_for_boundary_and_orientations(self):
        points,_=mesh()
        for a in np.linspace(0,2*math.pi,73):
            for radius in (0.,990.,1799.999,1800.):
                g=radius*np.array([math.cos(a),math.sin(a)])
                close=points[np.linalg.norm(points-g,axis=1)<=1000]-g
                for axis in np.linspace(0,2*math.pi,49):
                    self.assertGreaterEqual(np.max(close@np.array([math.cos(axis),math.sin(axis)])),-1e-8)

    def test_full_run_and_tampered_stop(self):
        case=make_case(41001,'outward');records=[]
        c=Client(Simulator(case),'SELF',records.append);r=run(c)
        self.assertTrue(audit(case,records,r)['passed'])
        altered=copy.deepcopy(r);altered['cleared']=[]
        with self.assertRaises(AssertionError):audit(case,records,altered)
        # Erasing scans for a truly absent channel must invalidate the proof even if all actual sources cleared.
        absent=next(ch for ch in range(1,21) if ch not in r['cleared'])
        ids={x['payload']['request_id'] for x in records if x['type']=='request' and x['payload'].get('channel')==absent}
        pruned=[x for x in records if x.get('request_id',x.get('payload',{}).get('request_id')) not in ids]
        with self.assertRaises(AssertionError):audit(case,pruned,r)

    def test_pure_optical_fallback_all_types_and_error_signs(self):
        for mode in ('positive','negative','smooth'):
            case=make_case(42000,'tangent',mode);records=[]
            c=Client(Simulator(case,rounding='pre_round_stress'),'SELF',records.append)
            r=run(c,{'localization':'optical'})
            self.assertTrue(audit(case,records,r)['passed'])

if __name__=='__main__':unittest.main()
