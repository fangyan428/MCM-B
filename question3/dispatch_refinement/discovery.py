"""Public-information discovery priorities; never supplies a stopping certificate.

A fixed 100 m area grid estimates each unknown channel's unexcluded region.
Uniform area weights are a scheduling heuristic, not a source distribution claim.
All receive, clear and stop decisions remain in the unchanged policy controller.
"""
from functools import lru_cache
import math

import numpy as np

from question3.innovation.geometry import bbox
from question3.innovation.routing import choose as choose_tour


@lru_cache(maxsize=8)
def _station_masks(stations):
    axis = np.arange(-1750.0, 1800.0, 100.0)
    xx, yy = np.meshgrid(axis, axis)
    points = np.column_stack((xx.ravel(), yy.ravel()))
    points = points[np.linalg.norm(points, axis=1) <= 1800.0]
    masks = np.linalg.norm(points[None, :, :] - np.asarray(stations)[:, None, :], axis=2) <= 1000.0
    masks.setflags(write=False)
    return masks


def _coverage_gains(scan_ids, context):
    known = set(context['first']) | set(context['cleared'])
    unknown = sorted(set(range(1, 21)) - known)
    stations = tuple(tuple(map(float, p)) for p in context['stations'])
    masks = _station_masks(stations)
    sums = {station: 0.0 for station in scan_ids}
    unresolved = 0
    for channel in unknown:
        excluded_stations = sorted(context['negative'].get(channel, set()))
        remaining = ~masks[excluded_stations].any(axis=0) if excluded_stations else np.ones(masks.shape[1], dtype=bool)
        count = int(remaining.sum())
        if not count:
            # A grid can miss a small real region: do not infer channel absence.
            unresolved += 1
            continue
        for station in scan_ids:
            sums[station] += float((masks[station] & remaining).sum()) / count
    # Public upper count supplies an optimistic discovery-value scale, not a
    # claimed estimate of how many sources actually remain.
    remaining_upper = max(0, 16 - len(known))
    scale = remaining_upper / len(unknown) if unknown else 0.0
    return {station: value * scale for station, value in sums.items()}, len(unknown), unresolved


def choose(current, tasks, context):
    """Return an existing (kind, id, point) task and JSON-compatible diagnostics.

    coverage_order: preserve the original tour's search/service choice; only
        reorder a selected search task using discovery value per estimated second.
    coverage_priority: compare that discovery value with one known-source service
        per estimated second. The service estimate uses its public region radius
        as an additional travel scale and one measurement; it is not a bound.
    """
    if not tasks:
        raise ValueError('Discovery dispatch requires at least one task')
    variant = context['config'].get('dispatch_variant', 'coverage_order')
    if variant not in ('coverage_order', 'coverage_priority'):
        raise ValueError('Unsupported discovery variant: ' + str(variant))
    original, route = choose_tour(current, tasks, True)
    details = dict(variant=variant, original_task=[original[0], int(original[1])],
                   original_route=route, grid_spacing_m=100.0,
                   value_model='uniform unexcluded area, scaled by remaining source-count upper bound',
                   scores=[])
    scans = [task for task in tasks if task[0] == 'scan']
    if not scans or (variant == 'coverage_order' and original[0] != 'scan'):
        return original, details
    gains, unknown_count, unresolved = _coverage_gains([task[1] for task in scans], context)
    details.update(unknown_channels=unknown_count, unresolved_grid_channels=unresolved)
    ranked = []
    for task in tasks:
        kind, ident, point = task
        travel = math.dist(current, point) / 5.0
        if kind == 'scan':
            # All still unknown channels may need a five-second measurement and
            # a one-second channel switch. Count-based early scan exit is ignored.
            cost = travel + 6.0 * unknown_count
            value = gains[ident]
        elif kind == 'localize' and variant == 'coverage_priority':
            radius = bbox(context['polys'][ident], context['bearings'][ident])[1]
            cost = travel + 5.0
            if radius > 20.0:
                cost += radius / 5.0 + 6.0
            value = 1.0
        else:
            continue
        score = value / max(cost, 1e-9)
        details['scores'].append(dict(task=kind, target=int(ident), value=value,
                                      estimated_seconds=cost, score=score))
        ranked.append((-score, cost, kind, int(ident), task))
    if not ranked or max(-row[0] for row in ranked) <= 0:
        # An unresolved grid or zero proxy never removes any required task.
        return original, details
    return min(ranked, key=lambda row: row[:4])[-1], details
