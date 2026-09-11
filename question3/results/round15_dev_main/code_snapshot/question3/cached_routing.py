"""Insertion cost of fully localized cached jobs; no source-location samples.

The full fixed optical path bounds every successful prefix followed by the anchor
by the triangle inequality. This is a single-job bound, not a global route bound.
"""
import math


def insertion_cost(current,points,anchor):
    distance=math.dist(current,points[0])
    distance+=sum(math.dist(a,b) for a,b in zip(points,points[1:]))
    distance+=math.dist(points[-1],anchor)-math.dist(current,anchor)
    return distance/5+3*len(points)+2


def reorder_cached(base,current,cover,remaining,jobs,cached):
    task,target,info=base
    if info.get('forced') or task!='localize' or target[1] not in cached or not remaining:
        return base
    anchor_id=min(remaining,key=lambda k:(math.dist(current,cover[k]),k))
    anchor=cover[anchor_id]
    costs={j[1]:insertion_cost(current,cached[j[1]][0],anchor) for j in jobs if j[1] in cached}
    original=target[1];chosen=min(costs,key=lambda c:(costs[c],c))
    # Keep the previous decision for numerical ties rather than introduce tie drift.
    if costs[original]<=costs[chosen]+1e-8:chosen=original
    target=next(j for j in jobs if j[1]==chosen)
    return task,target,dict(info,cache_routing='station_insertion',anchor_station_id=anchor_id,
                           insertion_costs_s=costs,original_channel=original,
                           cache_order_changed=chosen!=original)
