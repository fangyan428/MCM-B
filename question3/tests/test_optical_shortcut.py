import math
import unittest
import numpy as np
from question3.optical_shortcut import single_circle

class SingleCircleTests(unittest.TestCase):
    def test_diameter_circle_counterexample(self):
        # D=38 <40 is insufficient: the equilateral circumradius is >20.
        self.assertIsNone(single_circle([[0,0],[38,0],[19,19*math.sqrt(3)]]))
    def test_single_circle_covers_all_convex_combinations(self):
        v=np.array([[0,0],[30,0],[15,15*math.sqrt(3)]])
        p,r=single_circle(v);self.assertLess(r,20)
        rng=np.random.default_rng(11);w=rng.dirichlet([1,1,1],1000)
        self.assertLessEqual(np.linalg.norm(w@v-p,axis=1).max(),r+1e-8)
    def test_boundary_has_margin_and_fallback(self):
        self.assertIsNone(single_circle([[-20,0],[20,0]]))
        self.assertIsNotNone(single_circle([[-19.999,0],[19.999,0]]))
    def test_collinear_and_translated(self):
        p,r=single_circle([[1000,1000],[1010,1000],[1020,1000]])
        self.assertAlmostEqual(r,10);self.assertEqual(p,(1010.,1000.))
