"""Selective sharing must preserve ordinary batches and honest failure handling."""
import json
from pathlib import Path
import unittest
from question3.cases import random_case, late_source_case
from question3.interface import Client
from question3.simulator import Simulator
from question3.strategy import run


def config(limit=None):
    c=json.loads(Path('question3/configs/round10_dev/REF.json').read_text())
    if limit is not None:c['current_point_shared_limit']=limit
    return c


class CurrentSharingTests(unittest.TestCase):
    def test_current_cap_preserves_ordinary_batches_and_cached_measurements(self):
        for limit in [0,1,19]:
            events=[];requests=[];env=Simulator(random_case(0))
            result=run(Client(env,'SELF',requests.append),config(limit),events.append)
            modes={e['channel']:e['selection']['mode'] for e in events if e['type']=='localization'}
            stores=[e for e in events if e['type']=='shared_cache_store'];batches={}
            self.assertIn('opportunistic_current',modes.values())
            for e in stores:batches[e['primary_channel']]=batches.get(e['primary_channel'],0)+1
            for c,n in batches.items():
                if modes[c]=='opportunistic_current':self.assertLessEqual(n,limit)
            self.assertGreater(max(n for c,n in batches.items() if modes[c]!='opportunistic_current'),1)
            if limit:self.assertTrue(any(modes[c]=='opportunistic_current' for c in batches))
            for e in stores:
                ms=[q for q in requests if q['type']=='request' and q['path']=='/measure'
                    and q['payload']['channel']==e['channel'] and q['phase'].startswith('localization')]
                self.assertEqual(len(ms),1)
            self.assertEqual(result['status'],'complete');self.assertFalse(env.evaluation()['remaining_channels'])
            self.assertTrue(result['exit_confirmed'])

    def test_omitted_limit_is_exactly_existing_all_sharing(self):
        a=run(Client(Simulator(random_case(0)),'SELF'),config())
        b=run(Client(Simulator(random_case(0)),'SELF'),config(19))
        self.assertEqual(a,b)

    def test_late_channel_still_requires_coverage(self):
        r=run(Client(Simulator(late_source_case()),'SELF'),config(0))
        self.assertEqual(r['status'],'complete');self.assertIn(20,r['cleared_channels'])
        self.assertEqual(r['stopping_certificate']['method'],'seven_station_channel_cover')

    def test_current_measurement_contradiction_cannot_complete(self):
        client=Client(Simulator(random_case(0)),'SELF');original=client.measure;seen=[]
        def measure(p,c,phase='measure'):
            current=p==client.position
            r=original(p,c,phase)
            if phase=='localization' and current:
                seen.append(c);return {**r,'measure_result':'no_signal'}
            return r
        client.measure=measure
        r=run(client,config(0))
        self.assertTrue(seen);self.assertEqual(r['status'],'incomplete');self.assertFalse(r['exit_confirmed'])

    def test_bad_limit_rejected_before_enter(self):
        for limit in [-1,20,1.5,True,None]:
            c=config();c['current_point_shared_limit']=limit;client=Client(Simulator(random_case(0)),'SELF')
            with self.assertRaises(ValueError):run(client,c)
            self.assertFalse(client.entered)
