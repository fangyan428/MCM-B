"""Common complete workflow with optional modules A/B/C. Defaults preserve baseline_v1.
No imports of case generation/simulator; all decisions use public observations only.
"""
import math
from .geometry import stations, station_cover_bound, optical_plan
from .modules import choose_second,EvidenceCover
from .lookahead import decide

class Incomplete(RuntimeError):pass


def run(client, config, event=lambda data:None):
    cover=stations()
    if station_cover_bound()>=1000:raise ValueError('Invalid search coverage')
    negative={c:set() for c in range(1,21)};first={};cleared=set();regions=[];visited=set()
    modules=config.get('modules',{});joint=modules.get('B',False);evidence=modules.get('C',False)
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
    def localize(channel,q,selection):
        s,theta=first[channel];r=client.measure(q,channel,phase='localization')
        planner=None
        if r['measure_result']=='near':points=[q];certificate=dict(planned_clear_calls=1,covering_radius=5)
        elif r['measure_result']=='direction':
            points,certificate=optical_plan(s,theta,q,r['svd_deg'],config['error_deg'],config['optical_cell_m'],config['max_optical_points'])
            if evidence and len(points)<=128:
                planner=EvidenceCover(points,certificate,s,theta,q,r['svd_deg'],[cover[k] for k in sorted(negative[channel])],config['error_deg'])
            elif evidence:
                certificate['evidence_fallback']='more_than_128_coarse_cells_use_original_cover'
        else:raise Incomplete('Guaranteed-reception second point returned no_signal')
        certificate.update(channel=channel,first_position=s,second_position=q,selection=selection)
        regions.append(certificate);event(dict(type='localization',**certificate))
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
                q,sel=choose_second(*first[c],client.position,config)
                jobs.append((math.dist(client.position,q),c,q,sel))
            task,target,info=decide(client.position,client.channel,cover,remaining,jobs,first,negative,
                                    [c for c in range(1,21) if c not in first and c not in cleared],config,
                                    forced=bool(remaining and consecutive_localizations>=2))
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
