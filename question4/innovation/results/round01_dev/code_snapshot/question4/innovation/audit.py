"""Evaluator-only checks of logged conservative regions and optical evidence.

This module is called after policy execution. It imports no policy geometry and
does not lend the policy any source coordinates, directions or radii.
"""
import math
import numpy as np


TOLERANCE_M = 2e-5


def _vertices(row):
    vertices = np.asarray(row['vertices'], dtype=float)
    assert vertices.ndim == 2 and vertices.shape[1] == 2 and len(vertices), 'Malformed region'
    assert np.isfinite(vertices).all(), 'Nonfinite region'
    return vertices


def _inside(vertices, point):
    """Independent convex support-line test, including degenerate polygons."""
    point = np.asarray(point, dtype=float)
    assert point.shape == (2,) and np.isfinite(point).all(), 'Malformed point'
    low, high = vertices.min(axis=0), vertices.max(axis=0)
    if np.any(point < low-TOLERANCE_M) or np.any(point > high+TOLERANCE_M):
        return False
    edges = np.roll(vertices, -1, axis=0)-vertices
    lengths = np.linalg.norm(edges, axis=1)
    active = lengths > 1e-12
    if not active.any():
        return bool(np.linalg.norm(point-vertices[0]) <= TOLERANCE_M)
    offsets = point-vertices
    signed = (edges[:, 0]*offsets[:, 1]-edges[:, 1]*offsets[:, 0])[active]/lengths[active]
    return bool(np.all(signed >= -TOLERANCE_M) or np.all(signed <= TOLERANCE_M))


def _check_optical_rectangle(row, vertices, source):
    """Reconstruct the rectangular grid from public angle, independently.

    Historical pair-mode events omit the angle. Those only support a region
    containment audit and are explicitly counted separately in the result.
    """
    radius = float(row['cover_radius'])
    assert math.isfinite(radius) and 0 <= radius < 20, 'Invalid optical cell radius'
    count = row['points']
    assert isinstance(count, int) and not isinstance(count, bool) and count > 0, 'Invalid grid count'
    if 'angle' not in row:
        return False
    theta = math.radians(float(row['angle']))
    assert math.isfinite(theta), 'Nonfinite rectangle angle'
    axes = np.array([[math.cos(theta), -math.sin(theta)], [math.sin(theta), math.cos(theta)]])
    local = vertices @ axes
    low, high = local.min(axis=0)-1e-7, local.max(axis=0)+1e-7
    source_local = np.asarray(source) @ axes
    assert np.all(source_local >= low-TOLERANCE_M) and np.all(source_local <= high+TOLERANCE_M), 'Source outside optical rectangle'
    shape = np.maximum(1, np.ceil((high-low)/28).astype(int))
    assert int(np.prod(shape)) == count, 'Optical grid count mismatch'
    cell_width = (high-low)/shape
    expected_radius = float(np.linalg.norm(cell_width)/2)
    assert abs(expected_radius-radius) <= TOLERANCE_M, 'Optical cell radius mismatch'
    cell_index = np.clip(np.floor((source_local-low)/cell_width).astype(int), 0, shape-1)
    nearest = low+(cell_index+.5)*cell_width
    assert np.linalg.norm(source_local-nearest) <= radius+TOLERANCE_M, 'Grid misses true source'
    return True


def audit_regions(case, events):
    """Return audit counts or raise AssertionError for invalid logged evidence."""
    sources = {int(s['channel']): np.array([s['x'], s['y']], dtype=float) for s in case['sources']}
    counts = dict(passed=True, checked_regions=0, checked_clear_circles=0,
                  checked_optical_covers=0, optical_region_only=0,
                  checked_no_signal_unchanged=0)
    previous = {}
    for row in events:
        kind = row.get('event')
        if kind not in ('feasible_region', 'certified_clear', 'optical_cover'):
            continue
        channel = int(row['channel'])
        assert channel in sources, 'Region for nonexistent source'
        vertices = _vertices(row)
        source = sources[channel]
        assert _inside(vertices, source), f'True source excluded: channel {channel}, event {kind}'
        counts['checked_regions'] += 1
        if kind == 'feasible_region':
            if row.get('kind') == 'no_signal' and channel in previous:
                assert np.array_equal(vertices, previous[channel]), 'no_signal changed feasible region'
                counts['checked_no_signal_unchanged'] += 1
            previous[channel] = vertices.copy()
        elif kind == 'certified_clear':
            point = np.asarray(row['point'], dtype=float)
            radius = float(row['radius'])
            assert point.shape == (2,) and np.isfinite(point).all(), 'Malformed clear point'
            assert math.isfinite(radius) and 0 <= radius < 20, 'Invalid clear radius'
            assert np.linalg.norm(vertices-point, axis=1).max() <= radius+TOLERANCE_M, 'Clear circle excludes a region vertex'
            assert np.linalg.norm(source-point) <= 20+TOLERANCE_M, 'Clear circle misses true source'
            counts['checked_clear_circles'] += 1
        else:
            if _check_optical_rectangle(row, vertices, source):
                counts['checked_optical_covers'] += 1
            else:
                counts['optical_region_only'] += 1
    return counts
