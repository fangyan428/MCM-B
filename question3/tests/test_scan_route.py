"""Verify the finite path proxy independently and preserve complete workflow."""
import itertools
import json
import math
from pathlib import Path
import random
import unittest
from question3.scan_route import remaining_open_path
from question3.lookahead import decide
from question3.geometry import stations
from question3.cases import random_case,late_source_case
from question3.interface import Client
from question3.simulator import Simulator
from question3.strategy import run


def config():return json.loads(Path('question3/configs/round17_dev/ROUTE.json').read_text())


def cost(p,cover,path):
    total=0.
    for k in path:total+=math.dist(p,cover[k]);p=cover[k]
    return total


class ScanRouteTests(unittest.TestCase):
    def test_exact_cost_against_exhaustive_permutations(self):
        rng=random.Random(831);cover=stations(1125)
        for n in range(8):
            ids=rng.sample(range(7),n);p=(rng.uniform(-1800,1800),rng.uniform(-1800,1800))
            route,d=remaining_open_path(p,cover,ids)
            self.assertEqual(set(route),set(ids));self.assertEqual(len(route),n)
            self.assertAlmostEqual(d,cost(p,cover,route),places=8)
            self.assertAlmostEqual(d,min(cost(p,cover,x) for x in itertools.permutations(ids)),places=8)

    def test_greedy_counterexample_and_deterministic_tie(self):
        route,d=remaining_open_path((0,0),[(1,0),(-2,0),(3,0)],[0,1,2])
        self.assertEqual(route,(1,0,2));self.assertEqual(d,7)
        self.assertEqual(remaining_open_path((0,0),[(-1,0),(1,0)],[1,0]),((0,1),3.))

    def test_empty_singleton_and_duplicate_rejection(self):
        self.assertEqual(remaining_open_path((0,0),[],[]),((),0.))
        self.assertEqual(remaining_open_path((0,0),[(3,4)],[0]),((0,),5.))
        with self.assertRaises(ValueError):remaining_open_path((0,0),[(3,4)],[0,0])

    def test_longer_first_scan_still_competes_with_localization(self):
        cover=[(1,0),(-2,0),(3,0)];job=(1.5,10,(0,1.5),{})
        args=((0,0),None,cover,[0,1,2],[job],{}, {},[],config())
        task,target,info=decide(*args)
        self.assertEqual(task,'localize');self.assertEqual(target,job)
        self.assertEqual(info['scan_route'],[1,0,2]);self.assertEqual(info['scan_route_cost_m'],7)
        task,target,_=decide(*args[:-1],{})
        self.assertEqual((task,target),('scan',0))

    def test_real_controller_logs_valid_routes_and_retains_late_source(self):
        for case in [random_case(0),late_source_case()]:
            client=Client(Simulator(case),'SELF');cover=stations(config()['search_radius_m']);tasks=[]
            def check(e):
                if e['type']!='schedule':return
                tasks.append(e);route=e['scan_route']
                self.assertEqual(len(route),len(set(route)))
                self.assertAlmostEqual(e['scan_route_cost_m'],cost(client.position,cover,route),places=7)
                self.assertAlmostEqual(e['scan_route_cost_m'],min(cost(client.position,cover,p) for p in itertools.permutations(route)),places=7)
                if e['task']=='scan':self.assertEqual(route[0],e['station_id'])
            result=run(client,config(),check)
            self.assertEqual(result['status'],'complete');self.assertLessEqual(len(tasks),23)
            if case['id']=='late_channel20_after_ten':
                self.assertIn(20,result['cleared_channels'])
                self.assertEqual(result['stopping_certificate']['method'],'seven_station_channel_cover')

    def test_deadline_on_scan_never_reports_complete(self):
        client=Client(Simulator(late_source_case()),'SELF');n=0
        def expire(e):
            nonlocal n
            if e['type']=='schedule' and e['task']=='scan':
                n+=1
                if n==3:client.deadline=0
        result=run(client,config(),expire)
        self.assertEqual(n,3);self.assertEqual(result['status'],'incomplete');self.assertFalse(result['exit_confirmed'])

    def test_incompatible_or_unknown_config_rejected(self):
        for edits in [dict(scan_order='wrong'),dict(ring_phase='first_entry_radial'),dict(modules={})]:
            with self.assertRaises(ValueError):run(Client(Simulator(random_case(0)),'SELF'),{**config(),**edits})
