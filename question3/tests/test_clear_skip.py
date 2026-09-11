"""Geometric boundaries and whole-flow equivalence for execution-only skipping."""
import json
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch
import numpy as np
from question3.clear_skip import failure_certificate
from question3.cases import random_case,late_source_case
from question3.interface import Client,JsonlLog
from question3.audit import audit_folder
from question3.simulator import Simulator
from question3.strategy import run


def config(on=True):
    c=json.loads(Path('question3/configs/round11_dev/REF.json').read_text())
    if on:c['clear_skip']='separating_halfplane'
    return c


class ClearSkipTests(unittest.TestCase):
    def test_strict_disk_separation_and_inconclusive_corner(self):
        planes=(np.array([[1.,0.],[0.,1.]]),np.zeros(2))
        for p in [(20,0),(20+1e-6,0),(0,0),(-100,-100),(15,15)]:
            self.assertIsNone(failure_certificate(p,planes))
        self.assertIsNotNone(failure_certificate((20.001,0),planes))
        self.assertIsNone(failure_certificate((float('nan'),0),planes))
        self.assertIsNone(failure_certificate((100,100),None))

    def test_rotation_translation_normal_scaling(self):
        angle=.789;normal=np.array([np.cos(angle),np.sin(angle)])
        origin=np.array([1000000.,-1000000.])
        planes=(normal[None,:]*7,np.array([normal@origin*7]))
        self.assertIsNone(failure_certificate(origin+20*normal,planes))
        self.assertIsNotNone(failure_certificate(origin+20.01*normal,planes))

    def test_same_success_positions_and_measurements_on_fixed_cases(self):
        skipped=0
        for case in [random_case(i) for i in range(4)]+[late_source_case()]:
            runs=[]
            for enabled in [False,True]:
                req=[];es=[];env=Simulator(case)
                r=run(Client(env,'SELF',req.append),config(enabled),es.append)
                self.assertEqual(r['status'],'complete');self.assertFalse(env.evaluation()['remaining_channels'])
                requests={x['payload']['request_id']:x for x in req if x['type']=='request'}
                retained=[]
                for e in req:
                    if e['type']!='response':continue
                    q=requests[e['request_id']]
                    if q['path']=='/measure' or q['path']=='/clear' and e['response'].get('clear_result')=='success':
                        retained.append((q['path'],q['payload']['position'],q['payload']['channel']))
                runs.append((r,retained,es))
            self.assertEqual(runs[0][1],runs[1][1])
            self.assertLessEqual(runs[1][0]['metrics']['virtual_time_s'],runs[0][0]['metrics']['virtual_time_s']+1e-5)
            skipped+=sum(e['type']=='certified_clear_skip' for e in runs[1][2])
        self.assertGreater(skipped,0)

    def test_exhausted_skip_plan_never_claims_success(self):
        with patch('question3.strategy.failure_certificate',return_value=dict(halfplane_index=0,separation_m=100.,slack_m=1e-5)):
            r=run(Client(Simulator(random_case(0)),'SELF'),config())
        self.assertEqual(r['status'],'incomplete');self.assertFalse(r['exit_confirmed'])
        self.assertIn('All optical',r['failure'])

    def test_deadline_after_a_skip_is_incomplete(self):
        client=Client(Simulator(random_case(1)),'SELF');seen=[]
        def event(e):
            if e['type']=='certified_clear_skip':seen.append(e);client.deadline=0
        r=run(client,config(),event)
        self.assertTrue(seen);self.assertEqual(r['status'],'incomplete');self.assertFalse(r['exit_confirmed'])

    def test_independent_audit_rejects_forged_skip_witness(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);case=random_case(1)
            actions=JsonlLog(folder/'actions.jsonl');events=JsonlLog(folder/'strategy.jsonl')
            r=run(Client(Simulator(case),'SELF',actions),config(),events)
            actions.close();events.close()
            (folder/'evaluator_hidden_case.json').write_text(json.dumps(case))
            (folder/'result.json').write_text(json.dumps(dict(summary=dict(rounding='bounded'),strategy=r)))
            self.assertGreater(audit_folder(folder),0)
            rows=list(map(json.loads,(folder/'strategy.jsonl').read_text().splitlines()))
            skips=[e for e in rows if e['type']=='certified_clear_skip'];self.assertTrue(skips)
            skips[0]['separation_m']=1000000
            (folder/'strategy.jsonl').write_text('\n'.join(json.dumps(e) for e in rows)+'\n')
            with self.assertRaises(AssertionError):audit_folder(folder)

    def test_invalid_and_dynamic_plan_config_before_enter(self):
        for c in [{**config(),'clear_skip':'unknown'},{**config(),'modules':{**config()['modules'],'C':True}}]:
            client=Client(Simulator(random_case(0)),'SELF')
            with self.assertRaises(ValueError):run(client,c)
            self.assertFalse(client.entered)
