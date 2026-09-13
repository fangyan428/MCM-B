import copy
import json
import math
import threading
import unittest
from pathlib import Path
import numpy as np
from question2.strategy import candidate
from question3.cases import random_case,late_source_case,boundary_case,near_case
from question3.geometry import stations,station_cover_bound,optical_plan
from question3.interface import Client,HttpTransport,ProtocolError,TransportUncertain
from question3.simulator import Simulator
from question3.strategy import run
from question3.self_server import make_server

CONFIG=json.loads(Path('question3/configs/baseline.json').read_text())

def payload(i,**kw):return dict(arena_id='default',robot_id='SELF',request_id=str(i),**kw)

def source(c,x,y,r=1000):return dict(channel=c,x=x,y=y,radius=r)

class PhysicsTests(unittest.TestCase):
    def test_appendix_199_seconds_and_clear_channel(self):
        env=Simulator(dict(sources=[]));c=Client(env,'SELF');c.enter()
        self.assertEqual(c.measure((300,400),1)['virtual_time_s'],105)
        self.assertEqual(c.measure((300,400),2)['virtual_time_s'],111)
        self.assertEqual(c.clear((300,0),3)['virtual_time_s'],194)
        self.assertEqual(c.measure((300,0),2)['virtual_time_s'],199)
        self.assertEqual(c.channel,2);self.assertEqual(c.exit()['virtual_time_s'],199)
    def test_radius_and_near_and_clear_boundaries(self):
        c=Client(Simulator(dict(sources=[source(1,0,0)])),'SELF');c.enter()
        self.assertEqual(c.measure((1000,0),1)['measure_result'],'direction')
        self.assertEqual(c.measure((1000.0001,0),1)['measure_result'],'no_signal')
        self.assertEqual(c.measure((5,0),1)['measure_result'],'near')
        self.assertEqual(c.measure((5.0001,0),1)['measure_result'],'direction')
        self.assertEqual(c.clear((20.0001,0),1)['clear_result'],'no_target_in_range')
        self.assertEqual(c.clear((20,0),1)['clear_result'],'success')
        self.assertEqual(c.clear((0,0),1)['clear_result'],'no_target_in_range')
    def test_bias_fixed_at_same_location_and_bounded(self):
        for mode in ['spatial_hash','smooth','positive','negative']:
            c=Client(Simulator(dict(sources=[source(1,123,321,1500)],error_mode=mode)),'SELF');c.enter()
            self.assertEqual(c.measure((0.,0.),1)['svd_deg'],c.measure((-0.,-0.),1)['svd_deg'])
            for p in [(0,0),(700,100),(-100,-200)]:
                a=c.measure(p,1)['svd_deg'];b=c.measure(p,1)['svd_deg']
                self.assertEqual(a,b)
                true=math.degrees(math.atan2(321-p[1],123-p[0]))
                self.assertLessEqual(abs((a-true+180)%360-180),1+1e-10)
                self.assertAlmostEqual(a*100,round(a*100),places=7)
    def test_rounding_stress_enveloped(self):
        c=Client(Simulator(dict(sources=[source(1,123,321,1500)],error_mode='positive'),rounding='pre_round_stress'),'SELF');c.enter()
        a=c.measure((0,0),1)['svd_deg'];true=math.degrees(math.atan2(321,123))
        self.assertLessEqual(abs((a-true+180)%360-180),1.005+1e-10)
    def test_no_truth_fields(self):
        c=Client(Simulator(random_case(0)),'SELF')
        r=c.enter()
        self.assertEqual(set(r),{'accepted','real_timestamp_ms','virtual_time_s','max_virtual_duration_s','max_real_duration_s','remaining_real_duration_s'})
        r=c.measure((0,0),1)
        self.assertTrue(set(r)<={'accepted','real_timestamp_ms','virtual_time_s','measure_result','svd_deg'})

class ProtocolTests(unittest.TestCase):
    def test_idempotency_and_conflict(self):
        e=Simulator(dict(sources=[]));e.request('/enter',payload('e'))
        p=payload('m',position=dict(x=300,y=400),channel=1)
        a=e.request('/measure',p);b=e.request('/measure',p)
        self.assertEqual(a,b);self.assertEqual(e.evaluation()['virtual_time_s'],105)
        p['channel']=2;self.assertEqual(e.request('/measure',p)[0],409)
    def test_lost_response_same_id_exactly_once(self):
        e=Simulator(dict(sources=[]));seen=[]
        class Lost:
            def request(self,path,payload,timeout):
                r=e.request(path,payload,timeout);seen.append((path,copy.deepcopy(payload)))
                if path=='/measure' and len([x for x in seen if x[0]=='/measure'])==1:raise ConnectionError('Lost after commit')
                return r
        c=Client(Lost(),'SELF');c.enter();c.measure((300,400),1)
        self.assertEqual(seen[-1],seen[-2]);self.assertEqual(c.virtual,105)
        self.assertEqual(c.counts['measure'],1);self.assertEqual(c.counts['retries'],1)
    def test_rejected_clock_zero_does_not_reset(self):
        e=Simulator(dict(sources=[]));c=Client(e,'SELF');c.enter();c.measure((0,0),1)
        c.robot_id='WRONG'
        with self.assertRaises(ProtocolError):c.measure((0,0),2)
        self.assertEqual(c.virtual,5);self.assertEqual(c.channel,1)
    def test_failed_http_status_not_accepted(self):
        class Bad:
            def request(self,*args):return 500,dict(accepted=True,virtual_time_s=0)
        with self.assertRaises(ProtocolError):Client(Bad(),'SELF').enter()
    def test_uncertain_action_blocks_new_actions(self):
        class Broken:
            def request(self,*args):raise ConnectionError('down')
        c=Client(Broken(),'SELF')
        with self.assertRaises(TransportUncertain):c.enter()
        with self.assertRaises(ProtocolError):c.enter()
        self.assertEqual(c.virtual,0)
    def test_invalid_coordinate_no_effect(self):
        e=Simulator(dict(sources=[]));e.request('/enter',payload('e'))
        r=e.request('/measure',payload('m',position=dict(x=float('nan'),y=0),channel=1))
        self.assertEqual(r[0],400);self.assertEqual(e.evaluation()['virtual_time_s'],0)
    def test_unknown_field_rejected_without_id_consumption(self):
        e=Simulator(dict(sources=[]))
        p=payload('e',wrong=1);self.assertFalse(e.request('/enter',p)[1]['accepted'])
        del p['wrong'];self.assertTrue(e.request('/enter',p)[1]['accepted'])
    def test_deadline_incomplete(self):
        e=Simulator(random_case(0),remaining_s=0);c=Client(e,'SELF');r=run(c,CONFIG)
        self.assertEqual(r['status'],'incomplete');self.assertFalse(r['exit_confirmed'])
    def test_virtual_guard(self):
        c=Client(Simulator(dict(sources=[])),'SELF');c.enter();c.max_virtual=4
        with self.assertRaises(ProtocolError):c.measure((0,0),1)
        self.assertEqual(c.virtual,0)

class StrategyTests(unittest.TestCase):
    def test_seven_station_cover(self):
        self.assertLess(station_cover_bound(),1000)
        angles=np.linspace(0,2*np.pi,721);r=np.linspace(0,1800,41)
        points=np.array([(x*math.cos(a),x*math.sin(a)) for x in r for a in angles])
        nearest=np.linalg.norm(points[:,None,:]-np.array(stations())[None,:,:],axis=2).min(axis=1)
        self.assertLess(nearest.max(),1000)
    def test_q2_extended_error_certificate(self):
        self.assertTrue(candidate([800,605],20,1.005))
        self.assertFalse(candidate([800,0],20,1.005))
    def test_full_cases_stop_certificate(self):
        for case in [random_case(0),boundary_case(),late_source_case(),near_case()]:
            e=Simulator(case);r=run(Client(e,'SELF'),CONFIG)
            self.assertEqual(r['status'],'complete');self.assertEqual(e.evaluation()['remaining_channels'],[])
            cleared=set(r['cleared_channels'])
            for c in range(1,21):
                self.assertTrue(c in cleared or len(r['negative_station_ids'][str(c)])==7)
    def test_late_eleventh_source_not_omitted(self):
        e=Simulator(late_source_case());events=[];r=run(Client(e,'SELF'),CONFIG,events.append)
        self.assertIn(20,r['cleared_channels']);self.assertEqual(len(r['cleared_channels']),11)
        self.assertIn(20,next(row for row in events if row['type']=='coverage_complete')['detected'])
    def test_localization_contract_violation_incomplete(self):
        e=Simulator(random_case(0));events=[]
        class BadSecond:
            def request(self,path,payload,timeout):
                status,r=e.request(path,payload,timeout)
                if events and events[-1]['type']=='coverage_complete' and path=='/measure':
                    r['measure_result']='no_signal';r.pop('svd_deg',None)
                return status,r
        r=run(Client(BadSecond(),'SELF'),CONFIG,events.append)
        self.assertEqual(r['status'],'incomplete');self.assertFalse(r['exit_confirmed'])
    def test_optical_failure_is_not_success(self):
        e=Simulator(random_case(0))
        class BadClear:
            def request(self,path,payload,timeout):
                status,r=e.request(path,payload,timeout)
                if path=='/clear':
                    # Mimic impossible feedback AND accounting consistently.
                    if r.get('clear_result')=='success':
                        e._virtual_us-=2000000;e._components['laser_s']-=2
                        r['virtual_time_s']-=2;r['clear_result']='no_target_in_range'
                return status,r
        r=run(Client(BadClear(),'SELF'),CONFIG)
        self.assertEqual(r['status'],'incomplete');self.assertFalse(r['exit_confirmed'])
    def test_optical_grid_covers_polygon(self):
        first=(0,0);g=np.array([1499.,20.]);q=(800,605)
        b=math.degrees(math.atan2(g[1]-q[1],g[0]-q[0]))+.8
        points,cert=optical_plan(first,0,q,b,1.005,28,2000)
        self.assertLess(cert['covering_radius'],20)
        self.assertLessEqual(min(np.linalg.norm(np.array(p)-g) for p in points),20)
        # Random convex combinations cover interior, independent of chosen true G.
        rng=np.random.default_rng(5);v=np.array(cert['vertices'])
        w=rng.dirichlet(np.ones(len(v)),1000);samples=w@v
        self.assertLess(np.linalg.norm(samples[:,None,:]-np.array(points)[None,:,:],axis=2).min(axis=1).max(),20)
    def test_strategy_does_not_import_simulator(self):
        import ast
        root=ast.parse(Path('question3/strategy.py').read_text())
        imports=[n.module or '' for n in ast.walk(root) if isinstance(n,ast.ImportFrom)]
        self.assertTrue(all('simulator' not in x and 'cases' not in x for x in imports))

class HttpTests(unittest.TestCase):
    def test_complete_over_real_loopback_http(self):
        e=Simulator(late_source_case());server=make_server(e)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            client=Client(HttpTransport(f'http://127.0.0.1:{server.server_port}'),'SELF')
            r=run(client,CONFIG)
            self.assertEqual(r['status'],'complete');self.assertEqual(e.evaluation()['remaining_channels'],[])
        finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main(verbosity=2)
