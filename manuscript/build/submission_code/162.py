import json
from pathlib import Path
import unittest
from unittest.mock import patch
from question3.cases import random_case,late_source_case
from question3.interface import Client
from question3.simulator import Simulator
from question3.strategy import run
from question3.lookahead import decide
from question3.modules import choose_second


def cfg(n):return json.loads(Path('question3/configs/round9_dev',n+'.json').read_text())


class OpportunityTimingTests(unittest.TestCase):
    def test_scheduler_sees_only_original_catalog_jobs(self):
        calls=[];config=cfg('ZL');events=[]
        def spy(current,channel,cover,remaining,jobs,first,negative,unknown,c,forced=False):
            for _,source,q,selection in jobs:
                if selection['mode']=='shared_ready':continue
                original,_=choose_second(*first[source],current,{**c,'second_point_opportunity':'off'})
                self.assertEqual(q,original);self.assertEqual(selection['mode'],'cost_proxy')
            result=decide(current,channel,cover,remaining,jobs,first,negative,unknown,c,forced)
            calls.append(result);return result
        with patch('question3.strategy.decide',side_effect=spy):
            r=run(Client(Simulator(random_case(0)),'SELF'),config,events.append)
        self.assertTrue(calls);self.assertEqual(r['status'],'complete')
        last=None;checks=0
        for e in events:
            if e['type']=='schedule':last=e
            if e['type']=='second_point_after_schedule':
                self.assertEqual(last['task'],'localize');self.assertEqual(last['channel'],e['channel']);checks+=1
        self.assertGreater(checks,0)

    def test_cached_jobs_not_remeasured_and_late_source_found(self):
        for n in ['JL','ZL']:
            es=[];req=[];env=Simulator(late_source_case());r=run(Client(env,'SELF',req.append),cfg(n),es.append)
            self.assertEqual(r['status'],'complete');self.assertIn(20,r['cleared_channels'])
            cached={e['channel'] for e in es if e['type']=='shared_cache_store'}
            late={e['channel'] for e in es if e['type']=='second_point_after_schedule'}
            self.assertFalse(cached & late)
            for c in cached:
                measurements=[e for e in req if e['type']=='request' and e['path']=='/measure'
                    and e['payload']['channel']==c and e['phase'].startswith('localization')]
                self.assertEqual(len(measurements),1)

    def test_deadline_between_schedule_and_execution_is_incomplete(self):
        client=Client(Simulator(random_case(0)),'SELF');seen=[]
        def event(e):
            if e['type']=='second_point_after_schedule':seen.append(e);client.deadline=0
        r=run(client,cfg('ZL'),event)
        self.assertTrue(seen);self.assertEqual(r['status'],'incomplete');self.assertFalse(r['exit_confirmed'])

    def test_no_op_and_invalid_timing(self):
        c=cfg('REF');base=run(Client(Simulator(random_case(0)),'SELF'),c)
        c['opportunity_timing']='after_schedule'
        actual=run(Client(Simulator(random_case(0)),'SELF'),c)
        self.assertEqual(base,actual)
        c['opportunity_timing']='invalid';client=Client(Simulator(random_case(0)),'SELF')
        with self.assertRaises(ValueError):run(client,c)
        self.assertFalse(client.entered)
