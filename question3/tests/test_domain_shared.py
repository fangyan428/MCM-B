"""Channel-specific public ranges, full-sector fallback and shared-workflow failures."""
import json
from pathlib import Path
import unittest
from question3.shared_measurement import choose_shared
from question3.cases import random_case,clustered_case,late_source_case
from question3.interface import Client
from question3.simulator import Simulator
from question3.strategy import run


def config(name='BOTH'):return json.loads(Path('question3/configs/round19_dev',name+'.json').read_text())


class DomainSharedTests(unittest.TestCase):
    def test_each_channel_uses_own_first_range_and_exclusions(self):
        first={2:((1125.,0.),0.),1:((1125.,0.),0.),3:((0.,0.),0.)};point=(1425.,250.)
        self.assertIsNone(choose_shared(2,point,first,set(),{},config('PRIMARY')))
        c,s=choose_shared(2,point,first,set(),{},config())
        self.assertEqual(c,1);self.assertEqual(s['mode'],'domain_shared');self.assertEqual(s['source_range_upper_m'],676)
        self.assertIsNone(choose_shared(2,point,first,{1},{},config()))
        self.assertIsNone(choose_shared(2,point,first,set(),{1:None},config()))

    def test_old_eligibility_metadata_preserved(self):
        first={2:((1125.,0.),0.),1:((1125.,0.),0.)};point=(1625.,500.)
        a=choose_shared(2,point,first,set(),{},config('PRIMARY'))
        b=choose_shared(2,point,first,set(),{},config())
        self.assertEqual(a,b);self.assertEqual(b[1]['mode'],'shared_certified')

    def test_shared_retains_no_move_and_complete_late_source(self):
        for case in [random_case(0),late_source_case()]:
            env=Simulator(case);events=[];actions=[];result=run(Client(env,'SELF',actions.append),config(),events.append)
            self.assertEqual(result['status'],'complete');self.assertFalse(env.evaluation()['remaining_channels'])
            position=(0.,0.);moves={}
            for e in actions:
                if e['type']=='request' and e['path'] in ('/measure','/clear'):
                    p=e['payload']['position'];q=(p['x'],p['y']);c=e['payload']['channel']
                    if e['path']=='/measure' and e['phase']=='localization_shared':moves[c]=(position,q)
                    position=q
            for e in events:
                if e['type']=='localization' and e['selection']['mode']=='domain_shared':
                    a,b=moves[e['channel']];self.assertEqual(a,b)
            if case['id']=='late_channel20_after_ten':self.assertIn(20,result['cleared_channels'])

    def test_cluster_recovers_fifteen_shared_targets(self):
        times={}
        for variant in ['PRIMARY','BOTH']:
            env=Simulator(clustered_case());events=[];r=run(Client(env,'SELF'),config(variant),events.append)
            self.assertEqual(r['status'],'complete');self.assertFalse(env.evaluation()['remaining_channels'])
            times[variant]=r['metrics']['virtual_time_s']
            shares=[e for e in events if e['type']=='shared_cache_store']
            self.assertEqual(len(shares),15 if variant=='BOTH' else 0)
        self.assertLess(times['BOTH'],times['PRIMARY'])

    def test_failed_shared_measurement_is_incomplete(self):
        hit=False
        class BadClient(Client):
            def measure(self,p,c,phase='measure'):
                nonlocal hit
                r=super().measure(p,c,phase)
                if phase=='localization_shared':hit=True;return {**r,'measure_result':'no_signal'}
                return r
        r=run(BadClient(Simulator(clustered_case()),'SELF'),config())
        self.assertTrue(hit);self.assertEqual(r['status'],'incomplete');self.assertFalse(r['exit_confirmed'])

    def test_invalid_configuration_before_enter(self):
        for change in [dict(shared_range_prior='wrong'),dict(shared_selection='cost_gate'),dict(modules={'A':True,'B':True})]:
            client=Client(Simulator(random_case(0)),'SELF')
            with self.assertRaises(ValueError):run(client,{**config(),**change})
            self.assertFalse(client.entered)
