"""Experimental public-feedback policy. Imports no cases, simulator, files or RNG."""
import math
import numpy as np
from question3.geometry import stations,station_cover_bound
from question3.modules import choose_second
from .geometry import initial,wedge,bbox,enclosing,grid

def run(client,config,event=lambda row:None):
    cover=stations(1125)
    assert station_cover_bound(1125)<1000
    first={};polys={};bearings={};measured={};cleared=set();visited=set()
    negative={c:set() for c in range(1,21)}
    failure=None;exit_confirmed=False;certificate=None
    base=config['baseline_config']
    mode=config.get('mechanism','homing')
    def centre(c):
        return bbox(polys[c],bearings[c])[:2]
    def update(c,p,response):
        kind=response['measure_result']
        if kind=='near':
            if client.clear(p,c,phase='near')['clear_result']!='success':
                raise RuntimeError('Near feedback contradicted by failed clear')
            cleared.add(c)
            return
        if kind!='direction':
            raise RuntimeError('Certified reception returned no_signal')
        theta=response['svd_deg']
        if c not in first:
            first[c]=(tuple(p),theta)
            polys[c]=initial(p,theta,base['error_deg'])
            measured[c]=set()
        else:
            polys[c]=wedge(polys[c],p,theta,base['error_deg'])
        measured[c].add(tuple(p));bearings[c]=theta
        event(dict(type='feasible_update',channel=c,point=list(p),bearing=theta,vertices=polys[c].tolist()))
    def scan(k):
        p=cover[k]
        for c in range(1,21):
            if len(set(first)|cleared)==16:
                return
            if c in first or c in cleared:
                continue
            r=client.measure(p,c,phase='search')
            if r['measure_result']=='no_signal':negative[c].add(k)
            else:update(c,p,r)
        visited.add(k)
    def localize(c):
        for step in range(16):
            p,radius=centre(c)
            if radius<=20-1e-5:
                event(dict(type='certified_clear',channel=c,point=p.tolist(),radius=radius,vertices=polys[c].tolist()))
                if client.clear(p,c,phase='optical')['clear_result']!='success':
                    raise RuntimeError('Certified containing circle clear failed')
                cleared.add(c);return
            if radius>=1000-1e-5:
                raise RuntimeError('Adaptive measurement lacks reception certificate')
            if tuple(p) in measured[c]:
                break
            event(dict(type='certified_measure',channel=c,point=p.tolist(),radius=radius,vertices=polys[c].tolist()))
            update(c,p,client.measure(p,c,phase='adaptive_localization'))
            if c in cleared:return
        event(dict(type='finite_optical_fallback',channel=c,vertices=polys[c].tolist()))
        for p in grid(polys[c],bearings[c]):
            if client.clear(p,c,phase='optical_fallback')['clear_result']=='success':
                cleared.add(c);return
        raise RuntimeError('Finite optical cover exhausted without success')
    client.enter()
    try:
        while True:
            known=set(first)|cleared
            if len(known)>16:raise RuntimeError('Source count upper bound contradicted')
            pending=sorted(set(first)-cleared)
            remaining=[] if len(known)==16 else sorted(set(range(7))-visited)
            if not pending and not remaining:break
            jobs=[]
            for c in pending:
                # R1 keeps the baseline's pre-schedule second-point proxy.
                planning={**base,'second_point_opportunity':'off','second_range_prior':'off'}
                q,_=choose_second(*first[c],client.position,planning)
                jobs.append((math.dist(client.position,q),'localize',c))
            jobs += [(math.dist(client.position,cover[k]),'scan',k) for k in remaining]
            _,task,target=min(jobs)
            event(dict(type='schedule',task=task,target=target))
            if task=='scan':scan(target)
            else:localize(target)
        if len(cleared)==16:
            certificate=dict(method='source_count_upper_bound',source_upper_bound=16,
                successful_channels=sorted(cleared),inferred_absent_channels=sorted(set(range(1,21))-cleared))
        elif all(c in cleared or len(negative[c])==7 for c in range(1,21)):
            certificate=dict(method='seven_station_channel_cover')
        else:raise RuntimeError('Incomplete stopping certificate')
        if not 10<=len(cleared)<=16:raise RuntimeError('Clear count outside Q3 bounds')
        exit_confirmed=client.exit()['exit_reason']=='user_exit'
    except (RuntimeError,ValueError,KeyError) as exc:
        failure=f'{type(exc).__name__}: {exc}'
    result=dict(status='complete' if failure is None and exit_confirmed else 'incomplete',failure=failure,
        exit_confirmed=exit_confirmed,cleared_channels=sorted(cleared),
        absent_channels=sorted(c for c in negative if len(negative[c])==7),
        negative_station_ids={str(c):sorted(v) for c,v in negative.items()},
        station_positions=cover,stopping_certificate=certificate,regions=[],metrics=client.metrics())
    event(dict(type='strategy_result',**result))
    return result
