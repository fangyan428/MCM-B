"""O: same station+job task set, paired regret of incremental movement.
Public geometric samples are ranking proxies, never feasibility/stop certificates.
"""
import math
import numpy as np
from .lookahead import decide,stable_min,source_region_samples


def incremental_regrets(current,station,entry,terminals,anchor=None):
    terminals=np.asarray(terminals)
    # Difference = scan-first minus job-first; the same job's internal costs cancel.
    difference=math.dist(current,station)+math.dist(station,entry)-math.dist(current,entry)
    difference=difference-np.linalg.norm(terminals-np.asarray(station),axis=1)
    if anchor is not None:
        difference=difference+np.linalg.norm(terminals-np.asarray(anchor),axis=1)-math.dist(station,anchor)
    difference=difference/5
    return max(0.,float((-difference).max())),max(0.,float(difference.max())),difference


def decide_order(current,current_channel,cover,remaining,jobs,first,negative,unknown,config,cached,forced=False):
    base=decide(current,current_channel,cover,remaining,jobs,first,negative,unknown,config,forced)
    if forced or not remaining or not jobs:return base
    k=stable_min(remaining,lambda k:math.dist(current,cover[k]),lambda k:k)
    job=stable_min(jobs,lambda j:j[0],lambda j:j[1]);_,c,q,selection=job
    anchors=[cover[i] for i in remaining if i!=k]+[j[2] for j in jobs if j[1]!=c]
    anchor=min(anchors,key=lambda p:math.dist(current,p)) if anchors else None
    if c in cached:
        # Actual possible clearing stops; the same fixed optical prefix cancels.
        terminals=np.asarray(cached[c][0]);fallback=False;terminal_kind='cached_optical_points'
    else:
        s,bearing=first[c]
        terminals,fallback=source_region_samples(tuple(s),bearing,tuple(tuple(cover[i]) for i in sorted(negative[c])),config['error_deg'])
        terminal_kind='first_bearing_samples'
    regret_job,regret_scan,difference=incremental_regrets(current,cover[k],q,terminals,anchor)
    # Respect the old decision on numeric ties, rather than add another tie policy.
    task=('localize' if regret_job<regret_scan else 'scan') if abs(regret_job-regret_scan)>1e-8 else base[0]
    target=job if task=='localize' else k
    return task,target,dict(mode='same_task_order',forced=False,station_id_compared=k,channel_compared=c,
        anchor=anchor,job_first_regret_s=regret_job,scan_first_regret_s=regret_scan,
        scan_minus_job_range_s=[float(difference.min()),float(difference.max())],
        sample_count=len(terminals),sample_fallback=fallback,terminal_kind=terminal_kind,
        original_task=base[0],order_changed=task!=base[0])
