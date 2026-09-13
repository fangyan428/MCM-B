"""Finite batches preserve evidence, do not fake visits, and fail honestly."""
import json
from pathlib import Path
import unittest
from question3.batch_scheduling import gate
from question3.cases import random_case,late_source_case
from question3.interface import Client
from question3.simulator import Simulator
from question3.strategy import run


def config(name):return json.loads(Path('question3/configs/round15_dev',name+'.json').read_text())


class BatchSchedulingTests(unittest.TestCase):
    def test_cached_batch_filters_only_ready_jobs_without_mutating_evidence(self):
        jobs=[(1,2,(0,0),{}),(2,3,(1,1),{})];remaining=[1,2,3]
        selected,allowed,forced,info=gate('cached_batch',[2,3],{3:None},jobs,remaining,20)
        self.assertEqual([j[1] for j in selected],[3]);self.assertEqual(allowed,[]);self.assertFalse(forced)
        self.assertEqual(remaining,[1,2,3]);self.assertEqual(info['deferred_stations'],remaining)
        selected,allowed,forced,info=gate('cached_batch',[2],{},jobs[:1],remaining,20)
        self.assertEqual(allowed,remaining);self.assertTrue(forced);self.assertIsNone(info)

    def test_known_batch_keeps_all_known_jobs_and_returns_to_search(self):
        jobs=[(1,2,(0,0),{})]
        self.assertEqual(gate('known_batch',[2],{},jobs,[1],20)[:3],(jobs,[],False))
        self.assertEqual(gate('known_batch',[],{},[],[1],20)[:3],([],[1],True))

    def test_batch_selections_clear_at_most_sixteen_distinct_targets_between_scans(self):
        for mode in ['CACHE','KNOWN']:
            events=[];env=Simulator(random_case(0));r=run(Client(env,'SELF'),config(mode),events.append)
            self.assertEqual(r['status'],'complete');self.assertFalse(env.evaluation()['remaining_channels'])
            active=None;chain=[];batch_steps=0
            for e in events:
                if e['type']=='localization_batch':active=e;batch_steps+=1
                if e['type']=='schedule':
                    if active:
                        self.assertEqual(e['task'],'localize');self.assertIn(e['channel'],active['batch_channels']);active=None
                    if e['task']=='scan':chain=[]
                    else:
                        self.assertNotIn(e['channel'],chain);chain.append(e['channel']);self.assertLessEqual(len(chain),16)
            self.assertGreater(batch_steps,0)

    def test_late_channel_and_absence_certificate_not_replaced_by_queue_exhaustion(self):
        for mode in ['CACHE','KNOWN']:
            r=run(Client(Simulator(late_source_case()),'SELF'),config(mode))
            self.assertEqual(r['status'],'complete');self.assertIn(20,r['cleared_channels'])
            self.assertEqual(r['stopping_certificate']['method'],'seven_station_channel_cover')
            for c in r['absent_channels']:self.assertEqual(len(r['negative_station_ids'][str(c)]),7)

    def test_deadline_during_batch_is_not_complete(self):
        for mode in ['CACHE','KNOWN']:
            client=Client(Simulator(random_case(0)),'SELF');seen=[]
            def event(e):
                if e['type']=='localization_batch':seen.append(e);client.deadline=0
            r=run(client,config(mode),event)
            self.assertTrue(seen);self.assertEqual(r['status'],'incomplete');self.assertFalse(r['exit_confirmed'])

    def test_invalid_and_incompatible_mode_before_enter(self):
        for c in [{**config('KNOWN'),'search_interleaving':'both'},
                  {**config('KNOWN'),'modules':{**config('KNOWN')['modules'],'B':False}},
                  {**config('CACHE'),'modules':{**config('CACHE')['modules'],'S':False}}]:
            client=Client(Simulator(random_case(0)),'SELF')
            with self.assertRaises(ValueError):run(client,c)
            self.assertFalse(client.entered)

    def test_explicit_current_equals_omitted_setting(self):
        c=config('REF');a=run(Client(Simulator(random_case(0)),'SELF'),c)
        c['search_interleaving']='current';b=run(Client(Simulator(random_case(0)),'SELF'),c)
        self.assertEqual(a,b)
