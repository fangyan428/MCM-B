import copy
import json
import math
from pathlib import Path
import threading
import unittest
import numpy as np
from question3.cases import random_case,late_source_case
from question3.interface import Client,HttpTransport
from question3.simulator import Simulator
from question3.self_server import make_server
from question3.strategy import run
from question3.shared_measurement import compatible_offset,choose_shared
from question3.order_routing import incremental_regrets


def cfg(name):return json.loads(Path('question3/configs/round3_factorial',name+'.json').read_text())


class Round3Tests(unittest.TestCase):
    def test_shared_geometric_membership_and_exclusion(self):
        config=cfg('ABS');first={1:((0,0),0),2:((0,0),0),3:((0,0),0)}
        self.assertIsNotNone(compatible_offset((0,0),0,(800,605),1.005,20))
        self.assertIsNone(compatible_offset((0,0),0,(700,0),1.005,20))
        c,s=choose_shared(1,(800,605),first,set(),{2:True},config);self.assertEqual(c,3)
        self.assertIsNone(choose_shared(1,(800,605),first,{2},{3:True},config))
    def test_regret_matches_two_explicit_routes(self):
        x=(12,44);station=(700,100);q=(400,300);anchor=(-400,600);g=np.array([[1,2],[500,550]])
        rj,rs,d=incremental_regrets(x,station,q,g,anchor)
        direct=[]
        for z in g:
            jf=math.dist(x,q)+math.dist(q,z)+math.dist(z,station)+math.dist(station,anchor)
            sf=math.dist(x,station)+math.dist(station,q)+math.dist(q,z)+math.dist(z,anchor)
            direct.append((sf-jf)/5)
        np.testing.assert_allclose(d,direct);self.assertAlmostEqual(rj,max(0,-min(direct)));self.assertAlmostEqual(rs,max(0,max(direct)))
    def test_all_eight_complete_and_late_source(self):
        for path in sorted(Path('question3/configs/round3_factorial').glob('*.json')):
            env=Simulator(late_source_case());r=run(Client(env,'SELF'),cfg(path.stem))
            self.assertEqual(r['status'],'complete',(path.stem,r['failure']));self.assertIn(20,r['cleared_channels'])
            self.assertEqual(env.evaluation()['remaining_channels'],[])
    def test_shared_cached_once_no_extra_remeasure(self):
        events=[];requests=[];env=Simulator(random_case(0))
        r=run(Client(env,'SELF',requests.append),cfg('ABSOD'),events.append)
        stored=[e['channel'] for e in events if e['type']=='shared_cache_store'];used=[e['channel'] for e in events if e['type']=='shared_cache_use']
        self.assertGreater(len(stored),0);self.assertEqual(sorted(stored),sorted(used));self.assertEqual(len(stored),len(set(stored)))
        for c in stored:
            actions=[e for e in requests if e['type']=='request' and e['path']=='/measure' and e['payload']['channel']==c and e['phase'].startswith('localization')]
            self.assertEqual(len(actions),1);self.assertEqual(actions[0]['phase'],'localization_shared')
        self.assertEqual(r['status'],'complete')
    def test_search_cannot_be_starved_by_cached_jobs(self):
        events=[];r=run(Client(Simulator(random_case(0)),'SELF'),cfg('ABSOD'),events.append)
        scans=chain=0
        for e in events:
            if e['type']!='schedule':continue
            if e['task']=='scan':scans+=1;chain=0
            else:
                chain+=1
                if scans<7:self.assertLessEqual(chain,2)
        self.assertEqual(scans,7);self.assertEqual(r['status'],'complete')
    def test_no_signal_on_shared_measure_is_incomplete(self):
        class BadClient(Client):
            def measure(self,p,c,phase='measure'):
                r=super().measure(p,c,phase)
                if phase=='localization_shared':r={**r,'measure_result':'no_signal'}
                return r
        r=run(BadClient(Simulator(random_case(0)),'SELF'),cfg('ABSOD'))
        self.assertEqual(r['status'],'incomplete');self.assertIn('Guaranteed-reception',r['failure']);self.assertFalse(r['exit_confirmed'])
    def test_deadline_after_cache_is_not_complete(self):
        client=Client(Simulator(random_case(0)),'SELF');stored=[]
        def event(e):
            if e['type']=='shared_cache_store':stored.append(e);client.deadline=0
        r=run(client,cfg('ABSOD'),event)
        self.assertTrue(stored);self.assertEqual(r['status'],'incomplete');self.assertFalse(r['exit_confirmed'])
    def test_shared_response_retry_is_idempotent(self):
        env=Simulator(random_case(0));state={'phase':None,'lost':False}
        class DropOnce:
            def request(self,path,body,timeout):
                status,r=env.request(path,body,timeout)
                if not state['lost'] and path=='/measure' and state['phase']=='localization_shared':
                    state['lost']=True;raise OSError('accepted shared response lost')
                return status,r
        def log(e):
            if e['type']=='request':state['phase']=e['phase']
        r=run(Client(DropOnce(),'SELF',log),cfg('ABSOD'))
        self.assertTrue(state['lost']);self.assertEqual(r['status'],'complete');self.assertEqual(r['metrics']['counts']['retries'],1)
    def test_legacy_incompatible_config_rejected_before_enter(self):
        config=cfg('ABSOD');config['routing']={'mode':'region'};env=Simulator(random_case(0))
        with self.assertRaises(ValueError):run(Client(env,'SELF'),config)
        self.assertEqual(env.evaluation()['virtual_time_s'],0)
    def test_ABSOD_real_http(self):
        env=Simulator(random_case(0));server=make_server(env);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            r=run(Client(HttpTransport(f'http://127.0.0.1:{server.server_port}'),'SELF'),cfg('ABSOD'))
            self.assertEqual(r['status'],'complete');self.assertEqual(env.evaluation()['remaining_channels'],[])
        finally:server.shutdown();server.server_close();thread.join()
