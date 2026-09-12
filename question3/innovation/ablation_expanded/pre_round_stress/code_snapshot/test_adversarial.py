"""Self-only tests for nontrivial geometry, capability boundaries and safe failure."""
import ast
import json
import math
import random
import unittest
from pathlib import Path
import numpy as np
from .experiment import ROOT,PublicClient
from .geometry import initial,wedge,bbox,parallax_point,contains,worthwhile
from .coverage import covered,verify_cover_boxes
from .strategy import run
from question3.interface import Client
from question3.simulator import Simulator
from question3.cases import random_case,boundary_case,late_source_case,near_case,clustered_case
from question3.geometry import stations

BASE=json.loads((ROOT/'frozen/question3/configs/recommended_omni.json').read_text())
CONFIG=dict(baseline_config=BASE,mechanism='gated_tour_shared_parallax')

class Adversarial(unittest.TestCase):
    def test_extreme_bounded_geometry(self):
        rng=random.Random(611)
        for _ in range(600):
            theta=rng.uniform(0,360);r=rng.choice([5.0001,999.999,1000.,1499.999,1500.])
            angle=math.radians(theta);s=np.array([0.,0.]);g=np.array([r*math.cos(angle),r*math.sin(angle)])
            read=(theta+rng.choice([-1.005,1.005]))%360
            poly=initial(s,read)
            for step in range(12):
                self.assertTrue(contains(poly,g))
                q,R=bbox(poly,read)[:2]
                if R<20-1e-5:
                    self.assertLess(math.dist(q,g),20);break
                if step==0:q,R=parallax_point(poly,read,s)
                self.assertLess(R,1000)
                actual=math.degrees(math.atan2(*(g-q)[::-1]))
                read=(actual+rng.choice([-1.005,1.005]))%360
                poly=wedge(poly,q,read)
            else:self.fail('No contraction to terminal set in 12 steps')

    def test_wrap_and_near_boundary(self):
        for theta in [0.,.005,89.999,180.,270.,359.995]:
            for sign in [-1,1]:
                s=np.array([1125.,0.]);g=np.array([1800.,0.])
                actual=math.degrees(math.atan2(*(g-s)[::-1]))
                p=initial(s,(actual+sign*1.005)%360)
                self.assertTrue(contains(p,g))
            angle=math.radians(theta)
            g=np.array([1500*math.cos(angle),1500*math.sin(angle)])
            self.assertTrue(contains(initial([0,0],theta+1.005),g))

    def test_information_gate_covers_outputs(self):
        rng=random.Random(911)
        for _ in range(80):
            theta=rng.uniform(0,360);poly=initial([0,0],theta);q,R=parallax_point(poly,theta,[0,0])
            if not worthwhile(poly,theta,q):continue
            old=bbox(poly,theta)[1]
            for g in list(poly)+[(a+b)/2 for a,b in zip(poly,np.roll(poly,-1,axis=0))]:
                bearing=math.degrees(math.atan2(*(g-q)[::-1]))
                for error in (-1.005,0,1.005):
                    post=wedge(poly,q,bearing+error)
                    # Audit a valid bound with the new reading orientation; numerical enclosures may rotate.
                    self.assertLessEqual(bbox(post,bearing+error)[1],max(20,old/2)+1.)

    def test_coverage_certificate_independent(self):
        pts=stations(1125)
        self.assertTrue(covered(pts))
        self.assertGreater(verify_cover_boxes(pts)['covered_boxes'],0)
        for missing in range(7):self.assertFalse(covered(pts[:missing]+pts[missing+1:]))
        shifted=list(pts);shifted[-1]=(shifted[-1][0]+.01,shifted[-1][1])
        self.assertTrue(covered(shifted));verify_cover_boxes(shifted)

    def test_policy_has_no_oracle_or_file_access(self):
        forbidden={'open','eval','exec','getattr','setattr','__import__'}
        for name in ('strategy.py','geometry.py','routing.py'):
            tree=ast.parse((ROOT/name).read_text())
            for node in ast.walk(tree):
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):self.assertNotIn(node.func.id,forbidden)
                if isinstance(node,(ast.Import,ast.ImportFrom)):
                    names=[a.name for a in node.names] if isinstance(node,ast.Import) else [node.module or '']
                    self.assertFalse(any(any(k in n for k in ['simulator','cases','fixtures','pathlib','os','random','experiment']) for n in names))
                if isinstance(node,ast.Attribute):self.assertNotIn(node.attr,{'transport','_sources','_seed','_error_mode','evaluation','__dict__'})
        c=PublicClient(Client(Simulator(random_case(0)),'SELF'))
        self.assertFalse(hasattr(c,'transport'));self.assertFalse(hasattr(c,'evaluation'))

    def test_same_point_error_is_fixed(self):
        for mode in ['positive','negative','smooth','spatial_hash']:
            env=Simulator(random_case(0,mode));p=(100.125,-232.5)
            self.assertEqual(env._bias(p,7),env._bias(p,7))
            self.assertEqual(env._bias((0.,0.),7),env._bias((-0.,0.),7))

    def test_complete_adversarial_families(self):
        for case in [boundary_case(),late_source_case(),near_case(),clustered_case()]:
            env=Simulator(case);result=run(PublicClient(Client(env,'SELF')),CONFIG)
            self.assertEqual(result['status'],'complete',result['failure'])
            self.assertEqual(env.evaluation()['remaining_channels'],[])
            self.assertTrue(result['exit_confirmed'])

    def test_deadline_never_reports_complete(self):
        env=Simulator(random_case(0),remaining_s=0)
        result=run(PublicClient(Client(env,'SELF')),CONFIG)
        self.assertEqual(result['status'],'incomplete');self.assertFalse(result['exit_confirmed'])

    def test_rejected_clear_never_reports_complete(self):
        class Rejected(Simulator):
            def request(self,path,payload,timeout=5):
                if path=='/clear':return 200,dict(accepted=False,virtual_time_s=0)
                return super().request(path,payload,timeout)
        env=Rejected(random_case(0));result=run(PublicClient(Client(env,'SELF')),CONFIG)
        self.assertEqual(result['status'],'incomplete');self.assertFalse(result['exit_confirmed'])

    def test_certified_no_signal_never_reports_complete(self):
        class Corrupted(Simulator):
            def request(self,path,payload,timeout=5):
                status,response=super().request(path,payload,timeout)
                if path=='/measure':
                    p=(payload['position']['x'],payload['position']['y'])
                    if min(math.dist(p,s) for s in stations(1125))>1e-4:
                        response['measure_result']='no_signal';response.pop('svd_deg',None)
                return status,response
        env=Corrupted(random_case(0));result=run(PublicClient(Client(env,'SELF')),CONFIG)
        self.assertEqual(result['status'],'incomplete');self.assertFalse(result['exit_confirmed'])

if __name__=='__main__':unittest.main(verbosity=2)
