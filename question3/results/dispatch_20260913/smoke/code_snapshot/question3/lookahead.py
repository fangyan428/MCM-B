"""Round2: stable numerical ties and one-step terminal-region routing proxy.
No truth access. Scenario filtering affects scores only, never safety/stop proofs.
"""
import math
from functools import lru_cache
import numpy as np
from .scan_route import remaining_open_path


def stable_min(items,score,identity,tolerance=0.):
    if not items:return None
    best=min(score(x) for x in items)
    return min((x for x in items if score(x)<=best+tolerance),key=identity)


@lru_cache(maxsize=4096)
def source_region_samples(first,bearing,negative_positions,error_deg):
    delta=math.radians(error_deg);angle=math.radians(bearing)
    r,a=np.meshgrid(np.linspace(5.001,1500,31),angle+np.linspace(-delta,delta,3),indexing='ij')
    points=np.asarray(first)+np.column_stack([(r*np.cos(a)).ravel(),(r*np.sin(a)).ravel()])
    valid=np.linalg.norm(points,axis=1)<=1800+1e-7
    for pos in negative_positions:valid &= np.linalg.norm(points-pos,axis=1)>1000-1e-7
    filtered=points[valid]
    fallback=len(filtered)==0
    if fallback:filtered=points # Coarse samples are not an exact feasibility test.
    return filtered,fallback


def decide(current,current_channel,cover,remaining,jobs,first,negative,unknown,config,forced=False):
    """Jobs have (move_distance, channel, certified_q, A_selection).
    End samples are geometric proxies, not a probability distribution or error bound.
    """
    options=config.get('routing',{});tolerance=options.get('tie_tolerance_m',0.)
    mode=options.get('mode','nearest');weight=float(options.get('lookahead_weight',0.))
    if mode not in ('nearest','region','point'):raise ValueError('Unknown routing mode')
    if weight<0 or not math.isfinite(weight):raise ValueError('Invalid lookahead weight')
    if mode=='nearest':
        station=stable_min(remaining,lambda k:math.dist(current,cover[k]),lambda k:k,tolerance)
        route_info={}
        if config.get('scan_order','nearest')=='remaining_open_path':
            path,cost=remaining_open_path(current,cover,remaining)
            station=path[0] if path else None
            route_info=dict(scan_route_mode='remaining_open_path',scan_route=list(path),scan_route_cost_m=cost)
        job=stable_min(jobs,lambda j:j[0],lambda j:j[1],tolerance)
        choose_scan=station is not None and (job is None or forced or math.dist(current,cover[station])<=job[0]+tolerance)
        if choose_scan:return 'scan',station,dict(mode=mode,forced=forced,**route_info)
        return 'localize',job,dict(mode=mode,forced=False,**route_info)
    anchors=[('scan',k,cover[k]) for k in remaining]+[('localize',j[1],j[2]) for j in jobs]
    candidates=[]
    for k in remaining:
        other=[p for kind,ident,p in anchors if not (kind=='scan' and ident==k)]
        after=min((math.dist(cover[k],p) for p in other),default=0.)
        scan_cost=5*len(unknown)+max(0,len(unknown)-1)+(bool(unknown) and unknown[0]!=current_channel)
        score=math.dist(current,cover[k])/5+scan_cost+weight*after/5
        candidates.append(dict(kind='scan',id=k,score_s=float(score),forced=forced))
    if not forced:
        for _,c,q,selection in jobs:
            s,bearing=first[c]
            points,fallback=source_region_samples(tuple(s),bearing,tuple(tuple(cover[k]) for k in sorted(negative[c])),config['error_deg'])
            if mode=='point':points=points.mean(axis=0,keepdims=True)
            other=np.array([p for kind,ident,p in anchors if not (kind=='localize' and ident==c)])
            after=np.linalg.norm(points[:,None,:]-other[None,:,:],axis=2).min(axis=1) if len(other) else np.zeros(len(points))
            transit=np.linalg.norm(points-np.asarray(q),axis=1)+weight*after
            cells=selection.get('proxy_cells')
            if cells is None:raise ValueError('Lookahead currently requires A cost metadata')
            score=math.dist(current,q)/5+5+8.6*cells+float(transit.max())/5
            candidates.append(dict(kind='localize',id=c,score_s=score,sample_count=len(points),sample_fallback=fallback))
    chosen=stable_min(candidates,lambda x:x['score_s'],lambda x:(x['kind']!='scan',x['id']),tolerance/5)
    if chosen is None:raise RuntimeError('No routing task available')
    info=dict(mode=mode,weight=weight,forced=forced,chosen_score_s=chosen['score_s'],candidates=candidates)
    if chosen['kind']=='scan':return 'scan',chosen['id'],info
    return 'localize',next(j for j in jobs if j[1]==chosen['id']),info
