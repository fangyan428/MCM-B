import json
import math
from pathlib import Path
import threading
import unittest
import numpy as np
from question3.geometry import stations,station_cover_bound
from question3.strategy import run
from question3.interface import Client,HttpTransport
from question3.simulator import Simulator
from question3.cases import random_case
from question3.shared_measurement import choose_shared
from question3.self_server import make_server


def cfg(name):return json.loads(Path('question3/configs/round4_dev',name+'.json').read_text())


class Round4Tests(unittest.TestCase):
    def test_compressed_rings_continuous_bound_against_grid(self):
        r,a=np.meshgrid(np.linspace(0,1800,41),np.linspace(0,2*math.pi,721))
        points=np.column_stack([(r*np.cos(a)).ravel(),(r*np.sin(a)).ravel()])
        for rho in [1125,1200,1500]:
            bound=station_cover_bound(rho)
            d=np.linalg.norm(points[:,None,:]-np.asarray(stations(rho))[None,:,:],axis=2).min(axis=1)
            self.assertLess(bound,1000);self.assertLessEqual(float(d.max()),bound+1e-8)
    def test_boundary_midpoint_is_close_to_guarantee(self):
        p=(1800*math.cos(math.pi/6),1800*math.sin(math.pi/6))
        d=min(math.dist(p,q) for q in stations(1125))
        self.assertAlmostEqual(d,999.1106618753616);self.assertLess(d,1000)
    def test_unsafe_ring_rejected_before_enter(self):
        for rho in [1100,-1,float('nan')]:
            c=cfg('AB');c['search_radius_m']=rho;client=Client(Simulator(random_case(0)),'SELF')
            with self.assertRaises(ValueError):run(client,c)
            self.assertFalse(client.entered)
    def test_shared_gate_can_reject_a_geometrically_legal_point(self):
        first={1:((0,0),0),2:((0,0),0)};points=[(0,0),(100,0)]
        old=choose_shared(1,(400,500),first,set(),{},cfg('ABS'),points)
        gated=choose_shared(1,(400,500),first,set(),{},cfg('ABSG'),points)
        self.assertIsNotNone(old);self.assertIsNone(gated)
        self.assertIsNotNone(choose_shared(1,(800,605),first,set(),{},cfg('ABSG'),points))
    def test_adversarial_outer_midpoints_complete(self):
        sources=[]
        for c in range(1,13):
            a=(c%6+.5)*math.pi/3;sources.append(dict(channel=c,x=1800*math.cos(a),y=1800*math.sin(a),radius=1000.))
        case=dict(id='unit_outer_midpoints',seed=91,error_mode='positive',sources=sources)
        for name in ['ABR1125','ABSR1125G']:
            env=Simulator(case);r=run(Client(env,'SELF'),cfg(name))
            self.assertEqual(r['status'],'complete',r['failure']);self.assertEqual(env.evaluation()['remaining_channels'],[])
    def test_all_dev_configs_complete(self):
        for path in Path('question3/configs/round4_dev').glob('*.json'):
            env=Simulator(random_case(0));r=run(Client(env,'SELF'),cfg(path.stem))
            self.assertEqual(r['status'],'complete',(path.stem,r['failure']));self.assertEqual(env.evaluation()['remaining_channels'],[])
    def test_compressed_gate_over_real_http(self):
        env=Simulator(random_case(0));server=make_server(env);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            r=run(Client(HttpTransport(f'http://127.0.0.1:{server.server_port}'),'SELF'),cfg('ABSR1125G'))
            self.assertEqual(r['status'],'complete');self.assertEqual(env.evaluation()['remaining_channels'],[])
        finally:server.shutdown();server.server_close();thread.join()
