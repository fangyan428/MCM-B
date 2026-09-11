import json
import math
from pathlib import Path
import unittest
from question3.cached_routing import insertion_cost,reorder_cached
from question3.cases import late_source_case,random_case
from question3.interface import Client
from question3.simulator import Simulator
from question3.strategy import run


class CachedRoutingTests(unittest.TestCase):
    def test_full_path_bounds_all_successful_prefixes(self):
        current=(3,8);anchor=(100,20)
        for points in [[(10,0)],[(-30,20),(90,20),(45,60)],[(2,1),(2,1),(2,1)]]:
            bound=insertion_cost(current,points,anchor)
            for k in range(1,len(points)+1):
                prefix=insertion_cost(current,points[:k],anchor)
                self.assertLessEqual(prefix,bound+1e-9)
            direct=(math.dist(current,points[0])+sum(math.dist(a,b) for a,b in zip(points,points[1:]))
                    +math.dist(points[-1],anchor)-math.dist(current,anchor))/5+3*len(points)+2
            self.assertAlmostEqual(bound,direct)

    def test_insertion_can_choose_farther_entry(self):
        current=(0,0);cover=[(100,0)];cached={1:([(10,0),(-100,0)],{},None),2:([(20,0),(90,0)],{},None)}
        jobs=[(10,1,(10,0),{}),(20,2,(20,0),{})];base=('localize',jobs[0],{'forced':False})
        task,target,info=reorder_cached(base,current,cover,[0],jobs,cached)
        self.assertEqual(target[1],2);self.assertTrue(info['cache_order_changed'])
        for decision,remaining in [(('scan',0,{'forced':True}),[0]),(('scan',0,{'forced':False}),[0]),(base,[])]:
            self.assertEqual(reorder_cached(decision,current,cover,remaining,jobs,cached),decision)
        other=('localize',(1,3,(1,0),{}),{'forced':False})
        self.assertEqual(reorder_cached(other,current,cover,[0],jobs,cached),other)

    def test_existing_choice_on_equal_cost(self):
        job=(10,2,(10,0),{});jobs=[(10,1,(10,0),{}),job]
        cache={1:([(10,0)],{},None),2:([(10,0)],{},None)}
        answer=reorder_cached(('localize',job,{}),(0,0),[(100,0)],[0],jobs,cache)
        self.assertEqual(answer[1][1],2)

    def test_full_flow_and_search_fairness(self):
        config=json.loads(Path('question3/configs/round6_dev/I.json').read_text())
        for case in [late_source_case(),random_case(6,'smooth')]:
            events=[];env=Simulator(case);result=run(Client(env,'SELF'),config,events.append)
            self.assertEqual(result['status'],'complete');self.assertFalse(env.evaluation()['remaining_channels'])
            scans=chain=0
            for e in events:
                if e['type']!='schedule':continue
                if e['task']=='scan':scans+=1;chain=0
                else:
                    chain+=1
                    if scans<7:self.assertLessEqual(chain,2)
            self.assertEqual(scans,7)

    def test_incompatible_before_enter(self):
        config=json.loads(Path('question3/configs/round6_dev/I.json').read_text())
        for flag in ['C','O']:
            c={**config,'modules':{**config['modules'],flag:True}}
            client=Client(Simulator(random_case(0)),'SELF')
            with self.assertRaises(ValueError):run(client,c)
            self.assertFalse(client.entered)
