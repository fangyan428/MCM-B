"""Shortest open path through remaining public scan stations; no source data.

Exact for the stated static path proxy only. Localization interrupts the route,
and the count certificate may remove scans, so this is not total-time optimality.
"""
from functools import lru_cache
import math


def remaining_open_path(current,cover,remaining):
    ids=tuple(sorted(remaining))
    if len(ids)!=len(set(ids)) or len(ids)>7:raise ValueError('Expected at most seven distinct stations')
    if not ids:return (),0.
    @lru_cache(maxsize=None)
    def tail(last,mask):
        if not mask:return 0.,()
        choices=[]
        for j,k in enumerate(ids):
            if mask&(1<<j):
                cost,path=tail(k,mask^(1<<j))
                choices.append((math.dist(cover[last],cover[k])+cost,(k,)+path))
        return min(choices)
    choices=[];mask=(1<<len(ids))-1
    for j,k in enumerate(ids):
        cost,path=tail(k,mask^(1<<j))
        choices.append((math.dist(current,cover[k])+cost,(k,)+path))
    cost,path=min(choices)
    return path,cost
