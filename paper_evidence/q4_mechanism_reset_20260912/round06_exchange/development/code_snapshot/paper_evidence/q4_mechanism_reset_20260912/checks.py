"""Post-policy Q4 audit additions: continuous cover and fixed-point readings.

Only the evaluator calls this module, after the policy has returned. No source
coordinates are passed back to the policy. This supplements the historical
physical auditor; it does not mutate records, results, or old evidence.
"""
import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np
from scipy.spatial import ConvexHull, Delaunay


def _require(condition, message):
    if not condition:
        raise AssertionError(message)


def _point(value):
    p = tuple(float(x) for x in value)
    _require(len(p) == 2 and all(math.isfinite(x) for x in p), 'Invalid point')
    # Python numeric tuple equality identifies signed zero and int/float forms.
    return p


def _origin_segment_distance(a, b):
    edge = b-a
    length2 = float(edge @ edge)
    _require(length2 > 0, 'Zero-length coverage edge')
    t = min(1., max(0., float(-a @ edge)/length2))
    return float(np.linalg.norm(a+t*edge))


def _triangle_intersects_domain(vertices):
    edges = np.roll(vertices, -1, axis=0)-vertices
    signed = edges[:, 0]*(-vertices[:, 1])-edges[:, 1]*(-vertices[:, 0])
    inside = np.all(signed >= -1e-8) or np.all(signed <= 1e-8)
    return inside or min(_origin_segment_distance(vertices[i], vertices[(i+1) % 3])
                         for i in range(3)) <= 1800.+1e-7


@lru_cache(maxsize=64)
def _triangular_cover(serialized):
    """Rebuild a real planar mesh instead of trusting abstract edge counts.

    The full convex hull contains the target disk. Delaunay triangles partition
    that hull; each triangle touching the disk must have diameter below 1000 m.
    Triangles entirely outside the source disk may be larger (the historical
    31-station lattice has six such exterior fill triangles).
    """
    cert = json.loads(serialized)
    points = np.asarray(cert['stations'], dtype=float)
    _require(points.ndim == 2 and points.shape[1] == 2 and len(points) >= 3,
             'Malformed station array')
    _require(np.isfinite(points).all(), 'Nonfinite station')
    _require(len({tuple(p) for p in points}) == len(points),
             'Duplicate/coincident coverage stations')
    hull = ConvexHull(points)
    # scipy hull equations point outward, so each inequality must contain
    # the origin strictly; the nearest point on every polygon side must lie
    # beyond the source disk. Both tests are necessary.
    _require(np.max(hull.equations[:, -1]) < 0., 'Coverage hull misses origin')
    boundary = points[hull.vertices]
    min_boundary = min(_origin_segment_distance(boundary[i], boundary[(i+1) % len(boundary)])
                       for i in range(len(boundary)))
    _require(min_boundary >= 1800.-1e-7, 'Coverage hull does not contain source disk')
    rebuilt = Delaunay(points)
    rebuilt_keys = {tuple(sorted(map(int, tri))) for tri in rebuilt.simplices}
    claimed = cert.get('triangles')
    _require(isinstance(claimed, list) and len(claimed) > 0, 'Missing claimed triangles')
    claimed_keys = set()
    for tri in claimed:
        _require(isinstance(tri, list) and len(tri) == 3 and
                 all(isinstance(i, int) and not isinstance(i, bool) and 0 <= i < len(points)
                     for i in tri), 'Malformed triangle indices')
        _require(len(set(tri)) == 3, 'Repeated vertex in coverage triangle')
        key = tuple(sorted(tri))
        _require(key not in claimed_keys, 'Duplicate coverage triangle')
        claimed_keys.add(key)
        vertices = points[tri]
        cross = np.cross(vertices[1]-vertices[0], vertices[2]-vertices[0])
        _require(abs(float(cross)) > 1e-8, 'Degenerate coverage triangle')
        _require(key in rebuilt_keys, 'Claimed topology differs from rebuilt planar Delaunay mesh')
    relevant = 0
    max_diameter = 0.
    for tri in rebuilt.simplices:
        vertices = points[tri]
        if not _triangle_intersects_domain(vertices):
            continue
        relevant += 1
        _require(tuple(sorted(map(int, tri))) in claimed_keys,
                 'Claimed coverage omits a domain-intersecting triangle')
        diameter = float(np.linalg.norm(vertices[:, None]-vertices[None, :], axis=2).max())
        max_diameter = max(max_diameter, diameter)
        _require(diameter < 1000., 'Domain-intersecting triangle exceeds guaranteed range')
    _require(relevant > 0, 'No source-domain coverage triangles')
    return dict(kind='rebuilt_planar_delaunay', stations=len(points),
                relevant_triangles=relevant, full_hull_triangles=len(rebuilt.simplices),
                min_hull_edge_distance_m=min_boundary,
                max_relevant_triangle_diameter_m=max_diameter)


def check_additional(case, records, result, events):
    """Return audit counts or raise for unsupported completion evidence.

    `case` and `events` are accepted for the experiment runner's uniform audit
    interface. This check needs only public action records and the stop result.
    The historical physical/region auditor separately checks source truth.
    """
    del case, events
    requests, executed = {}, set()
    measured, readings, cleared = {}, {}, set()
    repeat_directions = 0
    entered = exited = False
    for row in records:
        if row.get('type') == 'request':
            request_id = row['payload']['request_id']
            if request_id in requests:
                old = requests[request_id]
                _require(old['path'] == row['path'] and old['payload'] == row['payload'],
                         'Request ID reused for a different action')
            requests[request_id] = row
            continue
        if row.get('type') != 'response':
            continue
        response = row['response']
        if row.get('http_status') != 200 or response.get('accepted') is not True:
            continue
        request_id = row['request_id']
        _require(request_id in requests, 'Accepted response without request evidence')
        if request_id in executed:
            continue
        executed.add(request_id)
        req = requests[request_id]
        path, body = req['path'], req['payload']
        _require(not exited, 'New accepted action after exit')
        if path == '/enter':
            _require(not entered, 'Second accepted enter')
            entered = True
        elif path == '/exit':
            _require(entered, 'Exit before enter')
            exited = True
        elif path in ('/measure', '/clear'):
            _require(entered, 'Accepted action before enter')
            p = _point((body['position']['x'], body['position']['y']))
            channel = int(body['channel'])
            if path == '/clear':
                if response['clear_result'] == 'success':
                    _require(channel not in cleared, 'Same source cleared twice')
                    cleared.add(channel)
                continue
            measured.setdefault(channel, set()).add(p)
            if response['measure_result'] == 'direction':
                reading = float(response['svd_deg'])
                _require(math.isfinite(reading), 'Nonfinite bearing')
                key = (channel, p)
                if key in readings:
                    difference = abs((reading-readings[key]+180.) % 360.-180.)
                    _require(difference <= 1e-12,
                             f'Same-point bearing changed: channel={channel}, point={p}')
                    repeat_directions += 1
                readings[key] = reading
        else:
            raise AssertionError('Unknown accepted action path')
    _require(entered and exited and result.get('status') == 'complete',
             'No accepted enter/exit and complete result')
    _require(set(result['cleared']) == cleared and len(result['cleared']) == len(cleared),
             'Cleared list differs from accepted successful actions')
    cert = result['stop_certificate']
    kind = cert.get('kind')
    if kind == 'count16':
        _require(len(cleared) == 16, 'Count16 stop without 16 successful distinct clears')
        coverage = dict(kind='count16', cleared=16)
        scanned_pairs = 0
    else:
        _require(kind in ('triangular_halfplane_cover', 'cell_halfplane_cover',
                         'dynamic_cell_halfplane_cover'),
                 'Unknown stop certificate kind')
        points = [_point(p) for p in cert['stations']]
        if kind == 'triangular_halfplane_cover':
            coverage = _triangular_cover(json.dumps(
                dict(stations=cert['stations'], triangles=cert['triangles']),
                sort_keys=True, separators=(',', ':'), allow_nan=False)).copy()
        else:
            import question4.audit as legacy
            if kind == 'dynamic_cell_halfplane_cover':
                contents = json.dumps(cert['dynamic_cover'], sort_keys=True,
                                      separators=(',', ':'), allow_nan=False).encode()
                _require(len(set(points)) == len(points), 'Duplicate dynamic stations')
            else:
                contents = (Path(legacy.__file__).with_name('certificates')/'compact22.json').read_bytes()
                _require(hashlib.sha256(contents).hexdigest() == cert['cover_sha256'],
                         'Compact continuous cover hash mismatch')
            expected = legacy.check_cover(contents)
            _require(np.array_equal(np.asarray(points), expected), 'Compact station list mismatch')
            coverage = dict(kind='independent_legacy_continuous_cell_cover', stations=len(points),
                            dynamic=kind == 'dynamic_cell_halfplane_cover',
                            cover_sha256=hashlib.sha256(contents).hexdigest())
        scanned_pairs = 0
        for channel in set(range(1, 21))-cleared:
            observed = measured.get(channel, set())
            _require(all(p in observed for p in points),
                     f'Coverage station omitted for uncleared channel {channel}')
            scanned_pairs += len(points)
    return dict(passed=True, stop=coverage,
                repeated_direction_observations_checked=repeat_directions,
                unique_direction_points=len(readings),
                actual_unresolved_channel_station_pairs_checked=scanned_pairs,
                accepted_actions_checked=len(executed))
