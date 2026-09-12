"""Evaluator-only deterministic adversarial geometry, never imported by policy.

These are development stress fixtures, not IID validation samples. The seed is
only the fixed spatial-error-field key. Geometry is explicit and deterministic.
"""
import hashlib
import json
import math
import copy
from pathlib import Path

from question3.interface import Client
from question4.simulator import Simulator


ROOT = Path(__file__).resolve().parent


def polar(radius, degrees):
    angle = math.radians(degrees)
    x, y = radius*math.cos(angle), radius*math.sin(angle)
    if math.hypot(x, y) > 1800:
        factor = math.nextafter(1800., 0.)/math.hypot(x, y)
        x, y = x*factor, y*factor
    return x, y


def source(channel, point, axis=None, radius=1000.):
    return dict(channel=channel, x=float(point[0]), y=float(point[1]),
                radius=float(radius), direction_deg=None if axis is None else float(axis % 360))


def ring(n, radius, phase, mode, directional=None, reception=1000.):
    directional = n-1 if directional is None else directional
    result = []
    for i in range(n):
        a = phase+i*360/n
        axis = {'outward': a, 'inward': a+180, 'tangent': a+90,
                'alternating_tangent': a+(90 if i % 2 else -90)}[mode]
        result.append(source(i+1, polar(radius, a), axis if i < directional else None, reception))
    return result


def make_fixtures():
    cases = []

    def add(name, sources, rationale, witnesses=None):
        seed = 491000+len(cases)
        cases.append(dict(id=f'{name}_{seed}_spatial_hash', seed=seed,
                          family=f'stress_{name}', error_mode='spatial_hash', sources=sources,
                          stress_metadata=dict(stage='development_adversarial_not_validation',
                              rationale=rationale, witnesses=witnesses or [])))

    add('boundary_outward_16', ring(16, 1800., 0., 'outward'),
        'Maximal source count; 15 outward emitters on the source-domain boundary with minimum reception radius.')
    add('boundary_inward_10', ring(10, 1800., 7., 'inward', directional=1),
        'Minimal count and one directional emitter; missing channels force a complete absence certificate.')
    add('boundary_tangent_16', ring(16, 1800., 3., 'tangent'),
        'Nearly all sources directional and tangent; localization transverse probes may hit the blind side.')
    add('boundary_alternating_12', ring(12, 1800., 15., 'alternating_tangent'),
        'Alternating tangent orientation at angles aligned with the outer-station phase.')

    sources = ring(12, 900., 0., 'tangent', directional=11)
    add('halfplane_boundary', sources,
        'Origin is mathematically on the closed emission-halfplane boundary for the 11 directional sources.',
        [dict(channel=1, point=[0., 0.], expected='direction', reason='Closed halfplane boundary at 900m.')])

    sources = ring(12, 900., 0., 'tangent', directional=11)
    for i, item in enumerate(sources[:-1]):
        item['direction_deg'] = (item['direction_deg']+(1e-6 if i % 2 == 0 else -1e-6)) % 360
    add('halfplane_sides', sources,
        'Alternating 1e-6 degree perturbations put the origin just inside/outside the emission halfplane.',
        [dict(channel=1, point=[0., 0.], expected='direction', reason='Just inside angular boundary.'),
         dict(channel=2, point=[0., 0.], expected='no_signal', reason='Just outside angular boundary.')])

    sources = [source(1, (3., 0.), 0.), source(2, (-4., 0.), 180.),
               source(3, (0., 4.9), 90.), source(4, (0., -4.9), 270.),
               source(5, (1., 1.), None)]
    sources += [source(i+6, polar(1200., i*360/11+11.), i*360/11+11. if i % 2 else None)
                for i in range(11)]
    add('near_backside_16', sources,
        'Four sources are strictly within 5m of origin but face away; an omnidirectional near source is present.',
        [dict(channel=i, point=[0., 0.], expected='no_signal', reason='Distance <5m does not override blind side.')
         for i in range(1, 5)]+
        [dict(channel=5, point=[0., 0.], expected='near', reason='Omnidirectional control within 5m.')])

    sources = [source(1, (5., 0.), 180.), source(2, (0., 5.), 90.),
               source(3, (-4.999999, 0.), 0.), source(4, (0., -5.000001), None)]
    sources += [source(i+5, polar(1650., 13.+i*60.), 13.+i*60. if i != 5 else None)
                for i in range(6)]
    add('near_threshold_10', sources,
        'Front/back examples at exactly 5m, just below 5m and just above 5m, plus distant minimum-radius sources.',
        [dict(channel=1, point=[0., 0.], expected='near', reason='Exactly 5m and facing origin.'),
         dict(channel=2, point=[0., 0.], expected='no_signal', reason='Exactly 5m on blind side.'),
         dict(channel=3, point=[0., 0.], expected='near', reason='Just below 5m and facing origin.'),
         dict(channel=4, point=[0., 0.], expected='direction', reason='Just above 5m, omnidirectional.')])

    sources = []
    for i in range(16):
        dx, dy = polar(7.+i*2.5, i*137.507764)
        sources.append(source(i+1, (1100.+dx, 200.+dy), None if i == 15 else i*137.507764))
    add('single_cluster_16', sources,
        'Tight 16-source cluster with varying directions; source service and early known-count stop compete with station routing.')

    sources = []
    for i in range(16):
        dx, dy = polar(9.+(i % 8)*3., i*137.507764)
        x = 1250. if i < 8 else -1250.
        sources.append(source(i+1, (x+dx, dy), None if i in (7, 15) else (0. if i < 8 else 180.)))
    add('opposite_clusters_16', sources,
        'Two dense antipodal clusters face outward; information-triggered routing can force expensive cross-domain revisits.')

    sources = []
    for i in range(10):
        angle = (20., 140., 260.)[i % 3]
        x, y = polar(1500., angle)
        dx, dy = polar(3.+i, i*109.)
        sources.append(source(i+1, (x+dx, y+dy), angle if i in (0, 3, 6, 9) else None))
    add('three_clusters_10', sources,
        'Ten sources in three separated compact groups; many absent channels prevent a count16 stop.')

    sources = ring(10, 1799.999999, 19., 'alternating_tangent', directional=8)
    for i, item in enumerate(sources):
        item['radius'] = 1000. if i % 2 else 1500.
    add('sparse_extreme_ranges_10', sources,
        'Sparse boundary sources alternate minimum and maximum reception radii; near tangency and absent channels coexist.')

    sources = []
    for direction in range(4):
        a = direction*90.
        for j, radius in enumerate((100., 700., 1300., 1800.)):
            ch = len(sources)+1
            sources.append(source(ch, polar(radius, a), None if ch == 16 else a))
    add('radial_collinear_16', sources,
        'Four radial chains with repeated bearing angles; second radio observations can be geometrically redundant.')

    sources = [source(1, (1000., 0.), 180.), source(2, (0., 1000.), 270.),
               source(3, (-1000., 0.), 0.), source(4, (0., -1000.), None),
               source(5, (999.999999, 0.), 180.), source(6, (1000.000001, 0.), 180.)]
    sources += [source(i+7, polar(1500., 31.+i*60.), 31.+i*60.+90 if i != 5 else None)
                for i in range(6)]
    add('reception_threshold', sources,
        'Exact minimum-radius boundary and points immediately inside/outside it, with visible directions.',
        [dict(channel=1, point=[0., 0.], expected='direction', reason='Exactly minimum reception radius.'),
         dict(channel=5, point=[0., 0.], expected='direction', reason='Just inside reception radius.'),
         dict(channel=6, point=[0., 0.], expected='no_signal', reason='Just outside reception radius.')])

    angles = [0.005, 30.0049999, 60.0050001, 90.005, 120.0049999, 150.0050001,
              180.005, 210.0049999, 240.0050001, 270.005, 300.0049999, 330.0050001]
    sources = [source(i+1, polar(1499.999999, a), None if i == 11 else a+180., 1500.)
               for i, a in enumerate(angles)]
    add('rounding_half_ticks', sources,
        'Origin bearings lie at or immediately around half-centidegree rounding ticks; cross global +/-1 errors and both rounding modes.')

    sources = ring(16, 1800., 11., 'alternating_tangent', directional=15)
    for i, item in enumerate(sources):
        item['radius'] = 1000. if i % 2 else 1500.
        if i % 3 == 0:
            item['direction_deg'] = None
    add('mixed_boundary_16', sources,
        'Mixed directional/omnidirectional sources at the domain boundary with alternating extreme reception radii.')
    return cases


def validate(cases):
    rows = []
    seen = set()
    for case in cases:
        sources = case['sources']
        assert 10 <= len(sources) <= 16
        assert len({s['channel'] for s in sources}) == len(sources)
        directional = sum(s['direction_deg'] is not None for s in sources)
        assert 1 <= directional < len(sources)
        assert all(1 <= s['channel'] <= 20 and 1000 <= s['radius'] <= 1500
                   and math.hypot(s['x'], s['y']) <= 1800 for s in sources)
        digest = hashlib.sha256(json.dumps(sources, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        assert digest not in seen
        seen.add(digest)
        checks = []
        for witness in case['stress_metadata']['witnesses']:
            client = Client(Simulator(case), 'SELF')
            client.enter()
            response = client.measure(witness['point'], witness['channel'], 'fixture_validation')
            assert response['measure_result'] == witness['expected'], (case['id'], witness, response)
            first_reading = response.get('svd_deg')
            again = client.measure(witness['point'], witness['channel'], 'fixture_repeat_validation')
            assert again['measure_result'] == response['measure_result']
            assert again.get('svd_deg') == first_reading
            client.exit()
            checks.append(dict(witness=witness, observed=response['measure_result'],
                               svd_deg=first_reading, repeat_identical=True))
        error_checks = []
        for mode in ('spatial_hash', 'positive', 'negative', 'smooth'):
            for rounding in ('bounded', 'pre_round_stress'):
                instance = copy.deepcopy(case)
                instance['error_mode'] = mode
                client = Client(Simulator(instance, rounding=rounding), 'SELF')
                client.enter()
                maximum_error = 0.
                for s in sources:
                    # Evaluator-owned response checks only. Geometry is never
                    # passed to a policy and no strategy is imported or run.
                    axis = 0. if s['direction_deg'] is None else s['direction_deg']
                    offset = polar(50., axis)
                    point = [s['x']+offset[0], s['y']+offset[1]]
                    if case['family'] == 'stress_rounding_half_ticks':
                        point = [0., 0.]
                    first = client.measure(point, s['channel'], 'fixture_error_validation')
                    second = client.measure(point, s['channel'], 'fixture_error_repeat_validation')
                    assert first['measure_result'] == second['measure_result'] == 'direction'
                    assert first['svd_deg'] == second['svd_deg']
                    true = math.degrees(math.atan2(s['y']-point[1], s['x']-point[0]))
                    error = abs((first['svd_deg']-true+180) % 360-180)
                    assert error <= (1.00000001 if rounding == 'bounded' else 1.00500001)
                    maximum_error = max(maximum_error, error)
                client.exit()
                error_checks.append(dict(error_mode=mode, rounding=rounding,
                    repeat_points_checked=len(sources), max_absolute_reading_error_deg=maximum_error,
                    all_repeats_identical=True))
        rows.append(dict(case_id=case['id'], source_count=len(sources), directional_count=directional,
                         max_source_radius_m=max(math.hypot(s['x'], s['y']) for s in sources),
                         sources_sha256=digest, valid=True, public_witness_checks=checks,
                         error_field_checks=error_checks))
    return rows


def main():
    cases = make_fixtures()
    rows = validate(cases)
    for name, data in [('fixtures.json', cases), ('fixture_validation.json', dict(
            stage='evaluator_only_fixture_validation_not_policy_benchmark',
            layouts=len(rows), passed=len(rows), rows=rows))]:
        (ROOT/name).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(layouts=len(cases), valid=len(rows), policies_run=0)))


if __name__ == '__main__':
    main()
