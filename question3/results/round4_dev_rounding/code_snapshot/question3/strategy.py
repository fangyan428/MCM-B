"""Common complete workflow with optional modules A/B/C. Defaults preserve baseline_v1.
No imports of case generation/simulator; all decisions use public observations only.
"""
import math
from .geometry import stations, station_cover_bound, optical_plan
from .modules import choose_second,EvidenceCover
from .lookahead import decide
from .optical_shortcut import single_circle
from .shared_measurement import choose_shared
from .order_routing import decide_order

class Incomplete(RuntimeError):pass


def run(client, config, event=lambda data:None):
    search_radius=config.get('search_radius_m',1500.)
    if station_cover_bound(search_radius)>=1000:raise ValueError('Invalid search coverage')
    cover=stations(search_radius)
    negative={c:set() for c in range(1,21)};first={};cleared=set();regions=[];visited=set()
    modules=config.get('modules',{});joint=modules.get('B',False);evidence=modules.get('C',False)
    shared=modules.get('S',False);order=modules.get('O',False);cached={}
    if (shared or order) and (not joint or config.get('routing',{}).get('mode','nearest')!='nearest'):
        raise ValueError('S/O require joint B with nearest routing; legacy H scoring is incompatible')
    if evidence and config['optical_cell_m']!=28:raise ValueError('Evidence module currently certifies 28m coarse cells only')
    client.enter();failure=None;exit_confirmed=False;coverage_emitted=False;consecutive_localizations=0
    def scan(station_id):
        s=cover[station_id]
        for channel in range(1,21):
            if channel in first or channel in cleared:continue
            response=client.measure(s,channel,phase='search');kind=response['measure_result']
            if kind=='no_signal':negative[channel].add(station_id)
            elif kind=='near':
                if client.clear(s,channel,phase='near')['clear_result']!='success':raise Incomplete('near followed by failed clear')
                cleared.add(channel)
            elif kind=='direction':first[channel]=(s,response['svd_deg'])
            else:raise Incomplete('Unknown measure result')
        visited.add(station_id)
    def prepare(channel,q,r,selection):
        s,theta=first[channel]
        planner=None
        if r['measure_result']=='near':points=[q];certificate=dict(planned_clear_calls=1,covering_radius=5)
        elif r['measure_result']=='direction':
            points,certificate=optical_plan(s,theta,q,r['svd_deg'],config['error_deg'],config['optical_cell_m'],config['max_optical_points'])
            shortcut=single_circle(certificate['vertices']) if modules.get('D',False) and len(points)>1 else None
            if shortcut:
                centre,radius=shortcut
                certificate.update(single_circle_centre=centre,original_grid_calls=len(points),
                                   planned_clear_calls=1,covering_radius=radius)
                points=[centre]
            elif evidence and len(points)<=128:
                planner=EvidenceCover(points,certificate,s,theta,q,r['svd_deg'],[cover[k] for k in sorted(negative[channel])],config['error_deg'])
            elif evidence:
                certificate['evidence_fallback']='more_than_128_coarse_cells_use_original_cover'
        else:raise Incomplete('Guaranteed-reception second point returned no_signal')
        certificate.update(channel=channel,first_position=s,second_position=q,selection=selection)
        regions.append(certificate);event(dict(type='localization',**certificate))
        return points,certificate,planner
    def localize(channel,q,selection):
        if channel in cached:
            points,certificate,planner=cached.pop(channel)
            event(dict(type='shared_cache_use',channel=channel,measurement_point=certificate['second_position'],
                       optical_entry=points[0]))
        else:
            r=client.measure(q,channel,phase='localization')
            points,certificate,planner=prepare(channel,q,r,selection)
            opportunity=choose_shared(channel,q,first,cleared,cached,config,primary_points=points,decision_log=event) if shared else None
            if opportunity:
                other,sel=opportunity
                response=client.measure(q,other,phase='localization_shared')
                cached[other]=prepare(other,q,response,sel)
                event(dict(type='shared_cache_store',channel=other,primary_channel=channel,point=q,
                           cached_channels=sorted(cached)))
        for i in range(len(points)):
            if planner:
                k,p,info=planner.next_point(client.position);event(dict(type='evidence_choice',channel=channel,point=p,**info))
            else:p=points[i]
            if client.clear(p,channel,phase='optical')['clear_result']=='success':
                cleared.add(channel)
                if planner:
                    certificate['evidence']=planner.metrics();event(dict(type='evidence_result',channel=channel,**planner.metrics()))
                break
            if planner:planner.failed(k)
        else:raise Incomplete('All optical covering points failed: model/protocol inconsistency')
    try:
        while True:
            pending=sorted(set(first)-cleared);remaining=sorted(set(range(len(cover)))-visited)
            if not remaining and not coverage_emitted:
                event(dict(type='coverage_complete',detected=sorted(first),cleared=sorted(cleared),
                           absent=[c for c in negative if len(negative[c])==len(cover)]));coverage_emitted=True
            if not pending and not remaining:break
            if not joint:
                if remaining:scan(remaining[0]);continue
                channel=pending[0];s,theta=first[channel];q,selection=choose_second(s,theta,client.position,config)
                localize(channel,q,selection);continue
            # B: choose nearest task start, force coverage after at most two localizations.
            jobs=[]
            for c in pending:
                if c in cached:
                    q=cached[c][0][0];sel=dict(mode='shared_ready',ready=True)
                else:q,sel=choose_second(*first[c],client.position,config)
                jobs.append((math.dist(client.position,q),c,q,sel))
            args=(client.position,client.channel,cover,remaining,jobs,first,negative,
                  [c for c in range(1,21) if c not in first and c not in cleared],config)
            forced=bool(remaining and consecutive_localizations>=2)
            task,target,info=decide_order(*args,cached=cached,forced=forced) if order else decide(*args,forced=forced)
            if task=='scan':
                event(dict(type='schedule',task='scan',station_id=target,**info))
                scan(target);consecutive_localizations=0
            else:
                _,c,q,sel=target;event(dict(type='schedule',task='localize',channel=c,**info))
                localize(c,q,sel);consecutive_localizations+=1
        if not all(c in cleared or len(negative[c])==len(cover) for c in range(1,21)):
            raise Incomplete('Stopping certificate is incomplete')
        if not 10<=len(cleared)<=16:raise Incomplete('Cleared count contradicts Q3 count bounds')
        exit_confirmed=client.exit()['exit_reason']=='user_exit'
    except (RuntimeError, ValueError, KeyError) as exc:
        failure=f'{type(exc).__name__}: {exc}'
    result=dict(status='complete' if failure is None and exit_confirmed else 'incomplete',failure=failure,
                exit_confirmed=exit_confirmed,cleared_channels=sorted(cleared),
                absent_channels=[c for c in negative if len(negative[c])==len(cover)],
                negative_station_ids={str(c):sorted(v) for c,v in negative.items()},station_positions=cover,
                regions=regions,metrics=client.metrics(),modules=modules)
    event(dict(type='strategy_result',**result));return result
