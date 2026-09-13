import json
import math
import unittest
from pathlib import Path
from question3.geometry import stations
from question3.lookahead import stable_min,source_region_samples
from question3.strategy import run
from question3.interface import Client
from question3.simulator import Simulator
from question3.cases import random_case,clustered_case

AB=json.loads(Path('question3/configs/round1/AB.json').read_text())

class LookaheadTests(unittest.TestCase):
    def test_tie_fix_real_station_geometry(self):
        ring=stations();ids=list(range(1,7))
        old=stable_min(ids,lambda k:math.dist((0,0),ring[k]),lambda k:k)
        new=stable_min(ids,lambda k:math.dist((0,0),ring[k]),lambda k:k,1e-7)
        rev=stable_min(ids[::-1],lambda k:math.dist((0,0),ring[k]),lambda k:k,1e-7)
        self.assertEqual(old,3);self.assertEqual(new,1);self.assertEqual(rev,1)
    def test_material_distance_not_overridden(self):
        data=[(1,1500.),(2,1499.)]
        self.assertEqual(stable_min(data,lambda x:x[1],lambda x:x[0],1e-7)[0],2)
    def test_old_AB_unchanged(self):
        r=run(Client(Simulator(random_case(0)),'SELF'),AB)
        self.assertEqual(r['metrics']['virtual_time_s'],6429.685179)
    def test_tie_cluster_regression(self):
        cfg={**AB,'routing':dict(mode='nearest',tie_tolerance_m=1e-7)}
        r=run(Client(Simulator(clustered_case()),'SELF'),cfg)
        self.assertEqual(r['status'],'complete');self.assertEqual(r['metrics']['virtual_time_s'],2239.)
    def test_all_modes_complete(self):
        for mode,weight in [('region',0),('region',.5),('region',1),('point',1)]:
            cfg={**AB,'routing':dict(mode=mode,lookahead_weight=weight,tie_tolerance_m=1e-7)}
            e=Simulator(random_case(0));r=run(Client(e,'SELF'),cfg)
            self.assertEqual(r['status'],'complete',r['failure']);self.assertEqual(e.evaluation()['remaining_channels'],[])
    def test_sampling_fallback_is_not_infeasibility(self):
        p,fallback=source_region_samples((0,0),0,((500.,0.),(1400.,0.)),1.005)
        self.assertTrue(fallback);self.assertGreater(len(p),0)

if __name__=='__main__':unittest.main(verbosity=2)
