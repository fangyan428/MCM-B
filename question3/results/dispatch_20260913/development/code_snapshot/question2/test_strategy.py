import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'question1'))
from solve import solve
from strategy import candidate, scenarios, diameters, to_world, DELTA

class StrategyTests(unittest.TestCase):
    def test_recommended_and_reflection(self):
        self.assertTrue(candidate([800,605]))
        self.assertTrue(candidate([800,-605]))
    def test_collinear_and_sideways_rejected(self):
        for q in [[0,0],[700,0],[0,500],[-10,100],[2000,500],[float('nan'),1]]:
            self.assertFalse(candidate(q))
    def test_continuous_conditions_against_dense_geometry(self):
        rng=np.random.default_rng(29)
        g,_=scenarios(121,31,1)
        r=np.linalg.norm(g,axis=1)
        qs=[[800,605],[800,-605],[500,500]]
        qs += [q for q in rng.uniform([0,0],[1000,1000],(100,2)) if candidate(q)]
        self.assertGreater(len(qs),10)
        for q in qs:
            d=np.linalg.norm(g-q,axis=1)
            self.assertTrue(np.all(d <= np.maximum(1000,r)+1e-7))
            self.assertTrue(np.all(d>5))
            cross=np.abs(g[:,0]*(g[:,1]-q[1])-g[:,1]*(g[:,0]-q[0]))
            self.assertTrue(np.all(cross/(r*d)>=np.sin(np.deg2rad(20))-1e-10))
    def test_vectorized_diameter_matches_question1(self):
        g,e=scenarios(7,3,3)
        q=[800,605]
        exact=diameters(q,g,e)
        for k in range(0,len(g),3):
            theta=np.rad2deg(np.arctan2(g[k,1]-q[1],g[k,0]-q[0])+e[k])%360
            result=solve([dict(x=0,y=0,bearing_deg=0),dict(x=q[0],y=q[1],bearing_deg=theta)])
            self.assertEqual(result['status'],'bounded')
            self.assertAlmostEqual(exact[k],result['diameter'],places=6)
    def test_frame_invariance(self):
        self.assertTrue(np.allclose(to_world([800,605],[100,-200],90),[-505,600]))
        g,e=scenarios(3,3,3);q=np.array([800,605]);j=7
        theta=np.rad2deg(np.arctan2(g[j,1]-q[1],g[j,0]-q[0])+e[j])
        world=to_world(q,[123,-456],359)
        result=solve([dict(x=123,y=-456,bearing_deg=359),dict(x=world[0],y=world[1],bearing_deg=(theta+359)%360)])
        self.assertAlmostEqual(diameters(q,g,e)[j],result['diameter'],places=6)
    def test_reflected_objective(self):
        g,e=scenarios(7,3,3)
        self.assertTrue(np.allclose(diameters([800,605],g,e),diameters([800,-605],g*[1,-1],-e)))
    def test_no_guarantee_for_perpendicular_move(self):
        g=np.array([1500.,0.]);q=np.array([0.,500.])
        self.assertGreater(np.linalg.norm(g-q),1500)
    def test_collinear_measurements_unbounded(self):
        # Collinear forward baseline has an unbounded overlap for a farther source.
        r=solve([dict(x=0,y=0,bearing_deg=0),dict(x=500,y=0,bearing_deg=0)])
        self.assertEqual(r['status'],'unbounded')

if __name__=='__main__':unittest.main(verbosity=2)
