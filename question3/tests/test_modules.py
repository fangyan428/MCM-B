import copy
import json
import math
import threading
import unittest
from pathlib import Path
import numpy as np
from question2.strategy import candidate
from question3.modules import EvidenceCover,design_catalog,choose_second
from question3.geometry import optical_plan
from question3.cases import random_case,late_source_case
from question3.interface import Client
from question3.interface import HttpTransport
from question3.self_server import make_server
from question3.simulator import Simulator
from question3.strategy import run

BASE=json.loads(Path('question3/configs/baseline.json').read_text())

class ModuleTests(unittest.TestCase):
    def test_A_all_candidates_analytically_safe(self):
        for row in design_catalog():self.assertTrue(candidate(row['offset'],20,1.005))
    def test_A_uses_current_position(self):
        cfg={**BASE,'modules':dict(A=True)}
        q1,_=choose_second((0,0),0,(800,1000),cfg)
        q2,_=choose_second((0,0),0,(800,-1000),cfg)
        self.assertGreater(q1[1],0);self.assertLess(q2[1],0)
    def test_default_baseline_frozen_time(self):
        env=Simulator(random_case(0));r=run(Client(env,'SELF'),BASE)
        self.assertEqual(r['metrics']['virtual_time_s'],10526.473544)
    def test_all_combinations_same_complete_contract(self):
        for name in ['baseline','A','B','C','AB','AC','BC','ABC']:
            cfg=json.loads(Path(f'question3/configs/round1/{name}.json').read_text())
            e=Simulator(late_source_case());r=run(Client(e,'SELF'),cfg)
            self.assertEqual(r['status'],'complete',(name,r['failure']))
            self.assertIn(20,r['cleared_channels']);self.assertEqual(e.evaluation()['remaining_channels'],[])
    def test_B_no_search_starvation(self):
        cfg={**BASE,'modules':dict(B=True)};events=[]
        r=run(Client(Simulator(random_case(0)),'SELF'),cfg,events.append)
        scans=0;chain=0
        for e in events:
            if e['type']!='schedule':continue
            if e['task']=='scan':scans+=1;chain=0
            else:
                chain+=1
                if scans<7:self.assertLessEqual(chain,2)
        self.assertEqual(scans,7);self.assertEqual(r['status'],'complete')
    def test_C_retains_true_cell_until_success(self):
        g=np.array([1499.,20.]);s=(0,0);q=(800,605);reading=math.degrees(math.atan2(g[1]-q[1],g[0]-q[0]))+.8
        points,cert=optical_plan(s,0,q,reading,1.005,28,2000)
        planner=EvidenceCover(points,cert,s,0,q,reading,[(0,-1000)],1.005)
        contains=np.all(g>=planner.corners.min(axis=1)-1e-8,axis=1)&np.all(g<=planner.corners.max(axis=1)+1e-8,axis=1)
        self.assertTrue(np.any(contains & planner.alive));current=q;success=False
        for _ in points:
            k,p,_=planner.next_point(current)
            if math.dist(p,g)<=20:success=True;break
            planner.failed(k);current=p
            self.assertTrue(np.any(contains & planner.alive))
        self.assertTrue(success)
    def test_C_whole_cell_cover_not_centre_heuristic(self):
        g=np.array([1499.,20.]);q=(800,605);reading=math.degrees(math.atan2(g[1]-q[1],g[0]-q[0]))
        points,cert=optical_plan((0,0),0,q,reading,1.005,28,2000)
        planner=EvidenceCover(points,cert,(0,0),0,q,reading,[],1.005)
        for k in range(len(points)):
            idx=planner.covers[k]
            self.assertTrue(np.all(np.linalg.norm(planner.corners[idx]-points[k],axis=2)<=20))
        self.assertTrue(np.all(planner.covers.any(axis=0)))
    def test_combined_budget_failure_not_complete(self):
        cfg={**BASE,'modules':dict(A=True,B=True,C=True)}
        result=run(Client(Simulator(random_case(0),remaining_s=0),'SELF'),cfg)
        self.assertEqual(result['status'],'incomplete');self.assertFalse(result['exit_confirmed'])
    def test_ABC_over_real_loopback_without_truth_fields(self):
        cfg={**BASE,'modules':dict(A=True,B=True,C=True)}
        env=Simulator(late_source_case());server=make_server(env)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            result=run(Client(HttpTransport(f'http://127.0.0.1:{server.server_port}'),'SELF'),cfg)
            self.assertEqual(result['status'],'complete')
            self.assertEqual(env.evaluation()['remaining_channels'],[])
        finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main(verbosity=2)
