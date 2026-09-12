"""Self-only adversarial tests for the directional mechanism migration."""
import copy
import math
import unittest
import numpy as np
from question3.interface import Client
from question4.audit import audit as audit_actions
from question4.geometry import first_region, bearing_clip, estimate
from question4.simulator import Simulator
from .audit import audit_regions, _inside
from .geometry import proposals, conditional_worthwhile
from .strategy import Strategy, run


def source(channel=1, x=100., y=0., direction=180., radius=1000.):
    return dict(channel=channel, x=x, y=y, radius=radius, direction_deg=direction)


def setup(sources, config=None, error_mode='zero', rounding='bounded'):
    case = dict(seed=6197, sources=sources, error_mode=error_mode)
    records, events = [], []
    client = Client(Simulator(case, rounding=rounding), 'SELF', records.append)
    policy = Strategy(client, config or {}, events.append)
    client.enter()
    return case, client, policy, records, events


class DirectionalMechanismTests(unittest.TestCase):
    def test_near_and_exact_direction_range_boundaries(self):
        _, client, _, _, _ = setup([source(x=0., direction=0.)])
        for point, expected in [((-4., 0.), 'no_signal'), ((4., 0.), 'near'),
                                ((0., 1000.), 'direction'), ((-1e-5, 999.), 'no_signal'),
                                ((1e-5, 999.), 'direction'), ((1000., 0.), 'direction'),
                                ((1000.0001, 0.), 'no_signal')]:
            with self.subTest(point=point):
                self.assertEqual(client.measure(point, 1)['measure_result'], expected)
        self.assertEqual(client.clear((-20., 0.), 1)['clear_result'], 'success')

    def test_positive_station_convex_hull_reception(self):
        rng = np.random.default_rng(2937)
        for axis in (0., 37., 90., 179.99, 270.):
            theta = math.radians(axis)
            rotate = np.array([[math.cos(theta), -math.sin(theta)], [math.sin(theta), math.cos(theta)]])
            positive = np.array([[0., 900.], [0., -900.], [900., 0.]]) @ rotate.T
            _, client, _, _, _ = setup([source(x=0., direction=axis)])
            for point in positive:
                self.assertNotEqual(client.measure(point, 1)['measure_result'], 'no_signal')
            for weights in rng.dirichlet(np.ones(3), 30):
                point = weights @ positive
                self.assertNotEqual(client.measure(point, 1)['measure_result'], 'no_signal')
            backside = np.array([-4., 0.]) @ rotate.T
            self.assertEqual(client.measure(backside, 1)['measure_result'], 'no_signal')

    def test_no_signal_preserves_region_and_finite_fallback(self):
        for mode in ('center', 'parallax'):
            case, client, policy, _, events = setup([source()], dict(mechanism=mode, adaptive_steps=16))
            policy.observe((0., 0.), 1, 'search')
            original = policy.known[1]['poly'].copy()
            policy.localize(1)
            attempts = [row for row in events if row.get('event') == 'adaptive_attempt']
            negative = [row for row in events if row.get('event') == 'feasible_region' and row['kind'] == 'no_signal']
            self.assertTrue(negative)
            self.assertLessEqual(len(attempts), 2)
            self.assertTrue(all(np.array_equal(original, row['vertices']) for row in negative))
            self.assertIn(1, policy.cleared)
            self.assertTrue(any(row.get('event') == 'optical_cover' for row in events))
            self.assertLess(client.counts['clear'], 120)
            self.assertTrue(audit_regions(case, events)['passed'])

    def test_conditional_positive_gate_can_receive_no_signal(self):
        case, client, policy, _, events = setup([source()], dict(sharing='gated'))
        policy.observe((0., 0.), 1, 'search')
        poly = policy.known[1]['poly'].copy()
        point = proposals(poly, 0., client.position, 'parallax')[0]
        self.assertTrue(conditional_worthwhile(poly, point))
        self.assertLess(np.linalg.norm(poly-point, axis=1).max(), 1000)
        client.measure(point, 20, 'test_positioning')
        policy.share(20)
        self.assertTrue(np.array_equal(poly, policy.known[1]['poly']))
        self.assertEqual(events[-1]['kind'], 'no_signal')
        attempt = next(row for row in events if row.get('event') == 'shared_attempt')
        self.assertFalse(attempt['reception_guaranteed'])
        self.assertTrue(attempt['conditional_gate'])
        measured = client.counts['measure']
        policy.share(20)
        self.assertEqual(client.counts['measure'], measured, 'Fixed point/channel must not be retried')
        self.assertEqual(audit_regions(case, events)['checked_no_signal_unchanged'], 1)

    def test_shared_near_clears_multiple_pending_channels(self):
        case, client, policy, _, events = setup(
            [source(2, 200., direction=None), source(3, 202., direction=None)], dict(sharing='gated'))
        policy.observe((-500., 0.), 2, 'search')
        policy.observe((-500., 0.), 3, 'search')
        client.measure((201., 0.), 1, 'test_positioning')
        # Near outcomes remain possible when this conservative conditional gate
        # rejects an expensive bearing: range sharing isolates safe mutation.
        policy.options['sharing'] = 'range'
        policy.share(1)
        self.assertEqual(policy.cleared, {2, 3})
        self.assertFalse(policy.known)
        self.assertFalse(policy._in_shared)
        self.assertEqual(client.counts['clear_success'], 2)
        self.assertEqual(client.channel, 3, 'Clearing must not switch the measurement channel')
        self.assertTrue(audit_regions(case, events)['passed'])

    def test_extreme_bearing_error_keeps_true_source(self):
        rng = np.random.default_rng(616027)
        for index in range(240):
            angle = rng.uniform(-math.pi, math.pi)
            radius = (1800. if index % 3 == 0 else rng.uniform(0., 1800.))
            truth = radius*np.array([math.cos(angle), math.sin(angle)])
            poly = None
            events = []
            for k in range(3):
                bearing = (359.999 if index % 5 == 0 and k == 0 else rng.uniform(0., 360.))
                error = (-1.005 if (index+k) % 2 else 1.005)
                distance = (1500. if index % 4 == 0 else rng.uniform(5.01, 1500.))
                theta = math.radians(bearing)
                point = truth-distance*np.array([math.cos(theta), math.sin(theta)])
                observed = (bearing+error) % 360
                poly = first_region(point, observed) if poly is None else bearing_clip(poly, point, observed)
                events.append(dict(event='feasible_region', channel=1, kind='direction', vertices=poly.tolist()))
            case = dict(sources=[source(x=float(truth[0]), y=float(truth[1]))])
            self.assertEqual(audit_regions(case, events)['checked_regions'], 3)

    def test_conditional_gate_covers_serialized_positive_outputs(self):
        poly = first_region((0., 0.), 359.999)
        point = proposals(poly, 359.999, (0., 0.), 'parallax')[0]
        self.assertTrue(conditional_worthwhile(poly, point))
        _, old = estimate(poly)
        # Enumerate possible true positions along polygon chords, with both
        # maximal errors. Compare posterior vertices to an independent circle.
        for blend in np.linspace(0., 1., 11):
            for vertex in poly:
                truth = blend*vertex+(1-blend)*poly.mean(axis=0)
                true_angle = math.degrees(math.atan2(*(truth-point)[::-1]))
                for error in (-1.005, 1.005):
                    posterior = bearing_clip(poly, point, (true_angle+error) % 360)
                    self.assertTrue(_inside(posterior, truth))
                    # The conditional gate promises an available covering
                    # circle, not an exact half-radius for every estimator.
                    center = posterior.mean(axis=0)
                    self.assertLess(np.linalg.norm(posterior-center, axis=1).max(), old)

    def test_independent_audit_rejects_tampered_region_and_circles(self):
        case = dict(sources=[source(x=0., y=0.)])
        vertices = [[-10., -10.], [10., -10.], [10., 10.], [-10., 10.]]
        event = dict(event='certified_clear', channel=1, vertices=vertices, point=[0., 0.], radius=math.sqrt(200))
        self.assertTrue(audit_regions(case, [event])['passed'])
        for mutation in ({'point': [50., 0.]}, {'radius': 5.}, {'vertices': [[30., 0.], [40., 1.], [40., -1.]]}):
            altered = copy.deepcopy(event); altered.update(mutation)
            with self.assertRaises(AssertionError):
                audit_regions(case, [altered])
        optical = dict(event='optical_cover', channel=1, vertices=vertices, angle=0.,
                       points=1, cover_radius=math.sqrt(2)*(10.+1e-7))
        self.assertEqual(audit_regions(case, [optical])['checked_optical_covers'], 1)
        for mutation in ({'points': 2}, {'cover_radius': 20.}, {'cover_radius': 1.}):
            altered = copy.deepcopy(optical); altered.update(mutation)
            with self.assertRaises(AssertionError):
                audit_regions(case, [altered])
        old = dict(event='feasible_region', channel=1, vertices=vertices, kind='direction')
        changed = dict(event='feasible_region', channel=1, vertices=(np.array(vertices)*.9).tolist(), kind='no_signal')
        with self.assertRaises(AssertionError):
            audit_regions(case, [old, changed])
        self.assertFalse(_inside(np.array([[0., 0.], [1., 0.]]), (2., 0.)))

    def test_complete_ten_and_sixteen_sources_late_channel_boundaries(self):
        for count, error, rounding in [(10, 'positive', 'bounded'), (16, 'negative', 'pre_round_stress')]:
            channels = list(range(1, count))+[20]
            sources = []
            for index, channel in enumerate(channels):
                theta = 2*math.pi*index/count
                axis = math.degrees(theta) if index % 2 == 0 else None
                sources.append(source(channel, 1800*math.cos(theta), 1800*math.sin(theta), axis))
            case = dict(sources=sources, seed=67213+count, error_mode=error)
            actions, events = [], []
            client = Client(Simulator(case, rounding=rounding), 'SELF', actions.append)
            result = run(client, dict(mechanism='parallax', sharing='gated'), events.append)
            self.assertEqual(len(result['cleared']), count)
            self.assertIn(20, result['cleared'])
            self.assertTrue(audit_actions(case, actions, result)['passed'])
            self.assertTrue(audit_regions(case, events)['passed'])
            self.assertEqual(result['stop_certificate']['kind'], 'count16' if count == 16 else 'triangular_halfplane_cover')


if __name__ == '__main__':
    unittest.main()
