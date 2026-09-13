import unittest
import numpy as np
from solve import solve, solve_halfplanes, bearing_halfplanes, triangle_measurements

class GeometryTests(unittest.TestCase):
    def test_rectangle(self):
        r = solve_halfplanes([[1,0],[-1,0],[0,1],[0,-1]], [3,0,4,0])
        self.assertAlmostEqual(r['diameter'], 5)
        self.assertTrue(r['diameter_circle_covers'])
    def test_actual_wedge_triangle_counterexample(self):
        r = solve(triangle_measurements())
        self.assertEqual(len(r['vertices']), 3)
        self.assertAlmostEqual(r['diameter'], 20, places=7)
        self.assertFalse(r['diameter_circle_covers'])
        self.assertAlmostEqual(r['max_distance_to_diameter_center'], 10*np.sqrt(3), places=7)
    def test_empty(self):
        self.assertEqual(solve_halfplanes([[1,0],[-1,0]], [0,-1])['status'], 'empty')
    def test_unbounded_wedge(self):
        self.assertEqual(solve([{'x':0,'y':0,'bearing_deg':0}])['status'], 'unbounded')
    def test_segment(self):
        r = solve_halfplanes([[1,0],[-1,0],[0,1],[0,-1]], [3,0,0,0])
        self.assertAlmostEqual(r['diameter'], 3)
    def test_point(self):
        r = solve_halfplanes([[1,0],[-1,0],[0,1],[0,-1]], [0,0,0,0])
        self.assertEqual(r['diameter'], 0)
    def test_wraparound_and_backward_rejection(self):
        A,b = bearing_halfplanes([{'x':0,'y':0,'bearing_deg':359.8}])
        self.assertTrue(np.all(A @ [100,0] <= b+1e-8))
        self.assertFalse(np.all(A @ [-100,0] <= b+1e-8))
    def test_parallel_duplicates(self):
        r=solve_halfplanes([[1,0],[-1,0],[0,1],[0,-1],[1,0]], [3,0,4,0,3])
        self.assertAlmostEqual(r['diameter'], 5)
    def test_negative_coordinates(self):
        r=solve_halfplanes([[1,0],[-1,0],[0,1],[0,-1]], [-1,4,-2,6])
        self.assertAlmostEqual(r['diameter'], 5)
    def test_random_true_source_containment(self):
        rng = np.random.default_rng(20260911)
        for _ in range(50):
            g=rng.uniform(-300,300,2)
            measurements=[]
            for angle in [0,120,240]:
                a=np.deg2rad(angle+rng.uniform(-10,10))
                s=g+600*np.array([np.cos(a),np.sin(a)])
                theta=np.rad2deg(np.arctan2(*(g-s)[::-1]))+rng.uniform(-1,1)
                measurements.append(dict(x=s[0], y=s[1], bearing_deg=theta%360))
            A,b=bearing_halfplanes(measurements)
            self.assertTrue(np.all(A@g <= b+1e-7))
            r=solve(measurements)
            self.assertEqual(r['status'],'bounded')
            v=np.array(r['vertices'])
            self.assertTrue(np.all(A@v.T <= b[:,None]+1e-7))
            # Independent projection lower bounds on diameter.
            for a in np.linspace(0,2*np.pi,20):
                projections=v@np.array([np.cos(a),np.sin(a)])
                self.assertLessEqual(np.ptp(projections),r['diameter']+1e-7)
    def test_invalid_input(self):
        with self.assertRaises(ValueError): solve([])
        with self.assertRaises(ValueError): solve([dict(x=float('nan'), y=0, bearing_deg=0)])

if __name__ == '__main__': unittest.main(verbosity=2)
