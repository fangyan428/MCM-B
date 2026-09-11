"""Batch invariants and adversarial interrupted-batch paths, without truth in policy."""
import json
from pathlib import Path
import unittest
from question3.cases import clustered_case,late_source_case
from question3.interface import Client
from question3.simulator import Simulator
from question3.strategy import run


def config():
    return json.loads(Path('question3/configs/round5_dev/COMPACT_BATCH.json').read_text())


class SharedBatchTests(unittest.TestCase):
    def test_multiple_shared_cached_once_and_full_certificate(self):
        events=[];requests=[];env=Simulator(clustered_case())
        result=run(Client(env,'SELF',requests.append),config(),events.append)
        stores=[e for e in events if e['type']=='shared_cache_store']
        self.assertGreater(max(len(e['cached_channels']) for e in stores),1)
        channels=[e['channel'] for e in stores]
        self.assertEqual(len(channels),len(set(channels)))
        self.assertEqual(sorted(channels),sorted(e['channel'] for e in events if e['type']=='shared_cache_use'))
        for c in channels:
            ms=[e for e in requests if e['type']=='request' and e['path']=='/measure'
                and e['payload']['channel']==c and e['phase'].startswith('localization')]
            self.assertEqual(len(ms),1)
        self.assertEqual(result['status'],'complete');self.assertFalse(env.evaluation()['remaining_channels'])
        for c in range(1,21):
            self.assertTrue(c in result['cleared_channels'] or len(result['negative_station_ids'][str(c)])==7)

    def test_second_shared_contradiction_cannot_certify_or_exit(self):
        class BadClient(Client):
            shared_count=0
            def measure(self,p,c,phase='measure'):
                r=super().measure(p,c,phase)
                if phase=='localization_shared':
                    self.shared_count+=1
                    if self.shared_count==2:r={**r,'measure_result':'no_signal'}
                return r
        client=BadClient(Simulator(clustered_case()),'SELF')
        r=run(client,config())
        self.assertEqual(client.shared_count,2);self.assertEqual(r['status'],'incomplete')
        self.assertFalse(r['exit_confirmed']);self.assertIn('Guaranteed-reception',r['failure'])

    def test_deadline_mid_batch_does_not_clear_cached_channels(self):
        client=Client(Simulator(clustered_case()),'SELF');stores=[]
        def event(e):
            if e['type']=='shared_cache_store':
                stores.append(e)
                if len(stores)==2:client.deadline=0
        r=run(client,config(),event)
        self.assertEqual(len(stores),2);self.assertEqual(r['status'],'incomplete')
        self.assertFalse(r['exit_confirmed'])
        self.assertTrue(all(e['channel'] not in r['cleared_channels'] for e in stores))

    def test_late_source_and_search_fairness(self):
        events=[];r=run(Client(Simulator(late_source_case()),'SELF'),config(),events.append)
        scans=chain=0
        for e in events:
            if e['type']!='schedule':continue
            if e['task']=='scan':scans+=1;chain=0
            else:
                chain+=1
                if scans<7:self.assertLessEqual(chain,2)
        self.assertEqual(scans,7);self.assertIn(20,r['cleared_channels']);self.assertEqual(r['status'],'complete')

    def test_invalid_batch_limit_before_enter(self):
        for limit in [0,20,1.5,True,None]:
            c=config();c['shared_batch_limit']=limit;client=Client(Simulator(clustered_case()),'SELF')
            with self.assertRaises(ValueError):run(client,c)
            self.assertFalse(client.entered)

    def test_explicit_one_preserves_default(self):
        c=config();c.pop('shared_batch_limit')
        a=run(Client(Simulator(clustered_case()),'SELF'),c)
        c['shared_batch_limit']=1;b=run(Client(Simulator(clustered_case()),'SELF'),c)
        self.assertEqual(a,b)
