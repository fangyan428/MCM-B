"""Published containing-circle bounds, independent from the unknown actual radius."""
import json
import tempfile
from pathlib import Path
import unittest
from question3.clear_skip import radius_failure_certificate
from question3.cases import random_case,late_source_case,clustered_case
from question3.interface import Client,JsonlLog
from question3.simulator import Simulator
from question3.strategy import run
from question3.audit import audit_folder


def config(name='BOTH'):
    return json.loads(Path('question3/configs/round13_dev',name+'.json').read_text())


class RadiusPriorTests(unittest.TestCase):
    def test_domain_tangent_and_uncertain_boundary_are_retained(self):
        for x in [0,1800,1820,1820+1e-6]:
            self.assertIsNone(radius_failure_certificate((x,0),(0,0),(100,0),'domain'))
        self.assertEqual(radius_failure_certificate((1820.001,0),(0,0),(100,0),'domain')['radius_prior'],'domain')

    def test_received_upper_bound_is_1500_not_minimum_radius(self):
        for x in [1100,1500,1520,1520+1e-6]:
            self.assertIsNone(radius_failure_certificate((x,0),(0,0),(0,0),'received'))
        proof=radius_failure_certificate((1520.001,0),(0,0),(0,0),'received')
        self.assertEqual(proof['containing_radius_m'],1500)

    def test_second_received_circle_and_mode_isolation(self):
        p=(0,0);first=(0,0);second=(1600,0)
        self.assertIsNone(radius_failure_certificate(p,first,second,'domain'))
        self.assertIsNone(radius_failure_certificate(p,first,second,'off'))
        self.assertEqual(radius_failure_certificate(p,first,second,'received')['radius_prior'],'second_received')

    def test_actual_skip_modes_keep_complete_clearance_and_measurements(self):
        for case in [random_case(0,'negative'),random_case(1,'smooth'),late_source_case(),clustered_case()]:
            trajectories=[];times=[];skipped=0
            for name in ['REF','DOMAIN','RANGE','BOTH']:
                records=[];events=[];env=Simulator(case)
                r=run(Client(env,'SELF',records.append),config(name),events.append)
                self.assertEqual(r['status'],'complete');self.assertFalse(env.evaluation()['remaining_channels'])
                req={e['payload']['request_id']:e for e in records if e['type']=='request'};trace=[]
                for e in records:
                    if e['type']!='response':continue
                    q=req[e['request_id']]
                    if q['path']=='/measure' or e['response'].get('clear_result')=='success':
                        trace.append((q['path'],q['payload'].get('channel'),q['payload'].get('position')))
                trajectories.append(trace);times.append(r['metrics']['virtual_time_s'])
                skipped+=sum(e['type']=='certified_clear_skip' and 'radius_prior' in e for e in events)
            self.assertTrue(all(t==trajectories[0] for t in trajectories))
            self.assertTrue(all(t<=times[0]+1e-5 for t in times))
            if case['id'].startswith('dev_'):self.assertGreater(skipped,0)

    def test_deadline_after_radius_skip_is_incomplete(self):
        client=Client(Simulator(random_case(0,'negative')),'SELF');seen=[]
        def event(e):
            if e['type']=='certified_clear_skip' and 'radius_prior' in e:seen.append(e);client.deadline=0
        r=run(client,config(),event)
        self.assertTrue(seen);self.assertEqual(r['status'],'incomplete');self.assertFalse(r['exit_confirmed'])

    def test_forged_smaller_radius_rejected_by_independent_audit(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);case=random_case(0,'negative')
            actions=JsonlLog(folder/'actions.jsonl');events=JsonlLog(folder/'strategy.jsonl')
            r=run(Client(Simulator(case),'SELF',actions),config(),events);actions.close();events.close()
            (folder/'evaluator_hidden_case.json').write_text(json.dumps(case))
            (folder/'result.json').write_text(json.dumps(dict(summary=dict(rounding='bounded'),strategy=r)))
            self.assertGreater(audit_folder(folder),0)
            rows=list(map(json.loads,(folder/'strategy.jsonl').read_text().splitlines()))
            e=next(e for e in rows if e['type']=='certified_clear_skip' and 'radius_prior' in e)
            e['containing_radius_m']-=100
            (folder/'strategy.jsonl').write_text('\n'.join(map(json.dumps,rows))+'\n')
            with self.assertRaises(AssertionError):audit_folder(folder)

    def test_invalid_or_disabled_parent_rejected_before_enter(self):
        for c in [{**config(),'clear_radius_priors':'unknown'},{**config(),'clear_skip':'off'}]:
            client=Client(Simulator(random_case(0)),'SELF')
            with self.assertRaises(ValueError):run(client,c)
            self.assertFalse(client.entered)
