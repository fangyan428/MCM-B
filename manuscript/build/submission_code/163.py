import json
import math
from pathlib import Path
import unittest
from question3.optical_order import nearer_end
from question3.cases import random_case,late_source_case
from question3.interface import Client
from question3.simulator import Simulator
from question3.strategy import run


def cfg(name='V'):
    return json.loads(Path('question3/configs/round6_factorial',name+'.json').read_text())


class OpticalOrderTests(unittest.TestCase):
    def test_same_cover_and_nonincreasing_full_traversal(self):
        p=[(10,0),(10,20),(0,20),(0,0)]
        for current in [(0,-1),(20,0),(5,0),(100,90)]:
            q=nearer_end(p,current)
            self.assertEqual(sorted(q),sorted(p))
            length=lambda points:math.dist(current,points[0])+sum(math.dist(a,b) for a,b in zip(points,points[1:]))
            self.assertLessEqual(length(q),length(p)+1e-9)
        self.assertIs(nearer_end(p,(5,0)),p)

    def test_order_events_match_actual_first_clear_including_cache(self):
        for name in ['V','IV']:
            merged=[];env=Simulator(random_case(0));r=run(Client(env,'SELF',merged.append),cfg(name),merged.append)
            self.assertEqual(r['status'],'complete');self.assertFalse(env.evaluation()['remaining_channels'])
            first_clears=set();entry={};cache_used=set();reversed_count=0
            for e in merged:
                if e['type']=='optical_path_order':
                    entry[e['channel']]=e['selected_entry'];reversed_count+=e['reversed']
                    self.assertGreaterEqual(e['entry_distance_saved_m'],-1e-8)
                if e['type']=='shared_cache_use':
                    cache_used.add(e['channel']);self.assertEqual(entry[e['channel']],e['optical_entry'])
                if e['type']=='request' and e['path']=='/clear' and e['phase']=='optical':
                    c=e['payload']['channel']
                    if c not in first_clears:
                        p=e['payload']['position'];self.assertEqual(tuple(entry[c]),(p['x'],p['y']));first_clears.add(c)
            self.assertTrue(cache_used);self.assertGreater(reversed_count,0)

    def test_reversed_path_exhaustion_is_incomplete(self):
        class BadClient(Client):
            def clear(self,p,c,phase='clear'):
                r=super().clear(p,c,phase)
                return {**r,'clear_result':'no_target_in_range'} if phase=='optical' else r
        r=run(BadClient(Simulator(random_case(0)),'SELF'),cfg())
        self.assertEqual(r['status'],'incomplete');self.assertFalse(r['exit_confirmed'])
        self.assertIn('All optical covering points failed',r['failure'])

    def test_late_channel_and_incompatible_evidence(self):
        result=run(Client(Simulator(late_source_case()),'SELF'),cfg('IV'))
        self.assertEqual(result['status'],'complete');self.assertIn(20,result['cleared_channels'])
        c=cfg();c['modules']['C']=True;client=Client(Simulator(random_case(0)),'SELF')
        with self.assertRaises(ValueError):run(client,c)
        self.assertFalse(client.entered)
