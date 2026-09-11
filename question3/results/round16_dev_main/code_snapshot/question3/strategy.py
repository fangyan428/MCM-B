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
from .cached_routing import reorder_cached
from .optical_order import nearer_end
from .clear_skip import constraints,failure_certificate,radius_failure_certificate
from .ring_phase import align_first_entry
from .batch_scheduling import gate as batch_gate

class Incomplete(RuntimeError):pass


def run(client, config, event=lambda data:None):
    opportunity=config.get('second_point_opportunity','off')
    if opportunity not in ('off','current_if_cheaper','current_if_certified'):
        raise ValueError('Unknown second_point_opportunity')
    if opportunity!='off' and not config.get('modules',{}).get('A',False):
        raise ValueError('Current-point comparison requires A')
    opportunity_timing=config.get('opportunity_timing','before_schedule')
    if opportunity_timing not in ('before_schedule','after_schedule'):
        raise ValueError('Unknown opportunity_timing')
    planning_config={**config,'second_point_opportunity':'off'} if opportunity_timing=='after_schedule' else config
    count_stop=config.get('count_stop','off')
    if count_stop not in ('off','cleared_16','detected_16'):
        raise ValueError('Unknown count_stop; Q3 source upper bound is fixed at 16')
    search_radius=config.get('search_radius_m',1500.)
    if station_cover_bound(search_radius)>=1000:raise ValueError('Invalid search coverage')
    empty_radius=config.get('empty_origin_radius_m')
    if empty_radius is not None and station_cover_bound(empty_radius)>=1000:
        raise ValueError('Invalid empty-origin search coverage')
    cover=stations(search_radius)
    negative={c:set() for c in range(1,21)};first={};cleared=set();regions=[];visited=set()
    modules=config.get('modules',{});joint=modules.get('B',False);evidence=modules.get('C',False)
    shared=modules.get('S',False);order=modules.get('O',False);cached={}
    phase_mode=config.get('ring_phase','fixed');phase_decided=False;station_phase=0.
    if phase_mode not in ('fixed','first_entry_radial'):raise ValueError('Unknown ring_phase')
    if phase_mode!='fixed' and not joint:raise ValueError('Adaptive ring phase requires B task selection')
    batch_mode=config.get('search_interleaving','current')
    if batch_mode not in ('current','cached_batch','known_batch','nearest_finite'):raise ValueError('Unknown search_interleaving')
    clear_skip=config.get('clear_skip','off');skip_planes={}
    if clear_skip not in ('off','separating_halfplane','separating_pair'):raise ValueError('Unknown clear_skip')
    if clear_skip!='off' and evidence:raise ValueError('Clear skipping requires the fixed optical path; C is incompatible')
    radius_priors=config.get('clear_radius_priors','off')
    if radius_priors not in ('off','domain','received','both'):raise ValueError('Unknown clear_radius_priors')
    if radius_priors!='off' and clear_skip=='off':raise ValueError('Radius priors require clear_skip')
    optical_order=config.get('optical_order','original')
    if optical_order not in ('original','nearer_end'):
        raise ValueError('Unknown optical_order')
    if optical_order!='original' and evidence:
        raise ValueError('Optical reversal requires a fixed optical path; C is incompatible')
    cache_route=config.get('cache_routing','nearest')
    if batch_mode!='current' and (not joint or order or cache_route!='nearest' or config.get('routing',{}).get('mode','nearest')!='nearest'):
        raise ValueError('Batch scheduling requires B nearest routing without O/cache insertion')
    if batch_mode=='cached_batch' and not shared:raise ValueError('Cached batch requires S')
    if cache_route not in ('nearest','station_insertion'):
        raise ValueError('Unknown cache_routing')
    if cache_route!='nearest' and (not shared or not joint or order or modules.get('C',False)):
        raise ValueError('Cache insertion requires B/S with fixed optical paths and O disabled')
    shared_limit=config.get('shared_batch_limit',1)
    if type(shared_limit) is not int or not 1<=shared_limit<=19:
        raise ValueError('shared_batch_limit must be an integer in [1,19]')
    current_shared_limit=config.get('current_point_shared_limit',shared_limit)
    if type(current_shared_limit) is not int or not 0<=current_shared_limit<=19:
        raise ValueError('current_point_shared_limit must be an integer in [0,19]')
    if (shared or order) and (not joint or config.get('routing',{}).get('mode','nearest')!='nearest'):
        raise ValueError('S/O require joint B with nearest routing; legacy H scoring is incompatible')
    if evidence and config['optical_cell_m']!=28:raise ValueError('Evidence module currently certifies 28m coarse cells only')
    client.enter();failure=None;exit_confirmed=False;coverage_emitted=False;consecutive_localizations=0
    stopping_certificate=None;count_discovery_emitted=False
    def scan(station_id):
        nonlocal phase_decided,station_phase
        if phase_mode!='fixed' and station_id!=0 and not phase_decided:
            # Only origin evidence exists. No already-observed outer point may move.
            if visited!={0} or any(ids-{0} for ids in negative.values()):
                raise Incomplete('Cannot rotate a ring after outer station evidence')
            old=cover[station_id];replacement,station_phase=align_first_entry(cover,station_id,client.position)
            cover[:]=replacement;phase_decided=True
            event(dict(type='ring_phase_selected',phase_rad=station_phase,station_id=station_id,
                       position=client.position,old_station=old,new_station=cover[station_id],
                       visited_before=sorted(visited),
                       local_movement_saved_s=(math.dist(client.position,old)-math.dist(client.position,cover[station_id]))/5))
        s=cover[station_id]
        for channel in range(1,21):
            # Q3 and Appendix 2 explicitly bound sources by 16 distinct channels.
            # Returning early does NOT mark this partially scanned station complete.
            if count_stop!='off' and len(cleared)==16:return
            if count_stop=='detected_16' and len(set(first)|cleared)==16:return
            if channel in first or channel in cleared:continue
            response=client.measure(s,channel,phase='search');kind=response['measure_result']
            if kind=='no_signal':negative[channel].add(station_id)
            elif kind=='near':
                if client.clear(s,channel,phase='near')['clear_result']!='success':raise Incomplete('near followed by failed clear')
                cleared.add(channel)
            elif kind=='direction':first[channel]=(s,response['svd_deg'])
            else:raise Incomplete('Unknown measure result')
        visited.add(station_id)
        if station_id==0 and empty_radius is not None and not first and not cleared:
            # Origin remains unchanged: its negatives stay valid for either certified ring.
            cover[:]=stations(empty_radius)
            event(dict(type='search_ring_switch',reason='all_twenty_origin_channels_no_signal',
                       configured_radius_m=search_radius,selected_radius_m=empty_radius))
    def prepare(channel,q,r,selection):
        s,theta=first[channel]
        planner=None
        if r['measure_result']=='near':points=[q];certificate=dict(planned_clear_calls=1,covering_radius=5)
        elif r['measure_result']=='direction':
            points,certificate=optical_plan(s,theta,q,r['svd_deg'],config['error_deg'],config['optical_cell_m'],config['max_optical_points'])
            if clear_skip!='off':skip_planes[channel]=constraints(s,theta,q,r['svd_deg'],config['error_deg'])
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
    def orient(channel,points):
        if optical_order=='original':return points
        chosen=nearer_end(points,client.position)
        event(dict(type='optical_path_order',channel=channel,reversed=chosen is not points,
                   original_entry=points[0],selected_entry=chosen[0],
                   entry_distance_saved_m=math.dist(client.position,points[0])-math.dist(client.position,chosen[0])))
        return chosen
    def localize(channel,q,selection):
        if channel in cached:
            points,certificate,planner=cached.pop(channel)
            points=orient(channel,points)
            event(dict(type='shared_cache_use',channel=channel,measurement_point=certificate['second_position'],
                       optical_entry=points[0]))
        else:
            if opportunity_timing=='after_schedule':
                planned=q
                q,selection=choose_second(*first[channel],client.position,config)
                event(dict(type='second_point_after_schedule',channel=channel,scheduled_point=planned,
                           actual_point=q,selection_mode=selection['mode'],point_changed=q!=planned))
            r=client.measure(q,channel,phase='localization')
            points,certificate,planner=prepare(channel,q,r,selection)
            points=orient(channel,points)
            batch_limit=current_shared_limit if selection['mode']=='opportunistic_current' else shared_limit
            for _ in range(batch_limit if shared else 0):
                opportunity=choose_shared(channel,q,first,cleared,cached,config,primary_points=points,decision_log=event)
                if opportunity is None:break
                other,sel=opportunity
                response=client.measure(q,other,phase='localization_shared')
                cached[other]=prepare(other,q,response,sel)
                event(dict(type='shared_cache_store',channel=other,primary_channel=channel,point=q,
                           cached_channels=sorted(cached)))
        for i in range(len(points)):
            if planner:
                k,p,info=planner.next_point(client.position);event(dict(type='evidence_choice',channel=channel,point=p,**info))
            else:p=points[i]
            if clear_skip!='off':
                proof=failure_certificate(p,skip_planes.get(channel),combine=clear_skip=='separating_pair')
                if proof is None and radius_priors!='off':
                    proof=radius_failure_certificate(p,first[channel][0],certificate['second_position'],radius_priors)
                if proof:
                    event(dict(type='certified_clear_skip',channel=channel,point=p,original_index=i,error_deg=config['error_deg'],**proof))
                    continue
            if client.clear(p,channel,phase='optical')['clear_result']=='success':
                cleared.add(channel)
                if planner:
                    certificate['evidence']=planner.metrics();event(dict(type='evidence_result',channel=channel,**planner.metrics()))
                break
            if planner:planner.failed(k)
        else:raise Incomplete('All optical covering points failed: model/protocol inconsistency')
    try:
        while True:
            known=set(first)|cleared
            if count_stop!='off' and len(known)>16:
                raise Incomplete('Observed source channels contradict Q3 upper bound 16')
            if count_stop!='off' and len(cleared)==16:break
            pending=sorted(set(first)-cleared);unvisited=sorted(set(range(len(cover)))-visited)
            count_saturated=count_stop=='detected_16' and len(known)==16
            remaining=[] if count_saturated else unvisited
            if count_saturated and not count_discovery_emitted:
                event(dict(type='source_upper_bound_saturated',source_upper_bound=16,
                           observed_channels=sorted(known),still_to_clear=pending,
                           unvisited_station_ids=unvisited))
                count_discovery_emitted=True
            if not unvisited and not coverage_emitted:
                event(dict(type='coverage_complete',detected=sorted(first),cleared=sorted(cleared),
                           absent=[c for c in negative if len(negative[c])==len(cover)]));coverage_emitted=True
            if not pending and not remaining:break
            if not joint:
                if remaining:scan(remaining[0]);continue
                channel=pending[0];s,theta=first[channel];q,selection=choose_second(s,theta,client.position,planning_config)
                localize(channel,q,selection);continue
            # B: choose nearest task start, force coverage after at most two localizations.
            jobs=[]
            ready_cache={c:(nearer_end(p,client.position),cert,planner) for c,(p,cert,planner) in cached.items()} if optical_order=='nearer_end' else cached
            for c in pending:
                if c in cached:
                    q=ready_cache[c][0][0];sel=dict(mode='shared_ready',ready=True)
                else:q,sel=choose_second(*first[c],client.position,planning_config)
                jobs.append((math.dist(client.position,q),c,q,sel))
            scheduled_jobs,scheduled_remaining,forced,batch_info=batch_gate(batch_mode,pending,cached,jobs,remaining,consecutive_localizations)
            if batch_info:event(dict(type='localization_batch',**batch_info))
            args=(client.position,client.channel,cover,scheduled_remaining,scheduled_jobs,first,negative,
                  [c for c in range(1,21) if c not in first and c not in cleared],config)
            decision=decide_order(*args,cached=ready_cache,forced=forced) if order else decide(*args,forced=forced)
            if cache_route=='station_insertion':
                decision=reorder_cached(decision,client.position,cover,remaining,jobs,ready_cache)
            task,target,info=decision
            if task=='scan':
                event(dict(type='schedule',task='scan',station_id=target,**info))
                scan(target);consecutive_localizations=0
            else:
                _,c,q,sel=target;event(dict(type='schedule',task='localize',channel=c,**info))
                localize(c,q,sel);consecutive_localizations+=1
        if count_stop!='off' and len(cleared)==16:
            stopping_certificate=dict(method='source_count_upper_bound',source_upper_bound=16,
                successful_channels=sorted(cleared),
                inferred_absent_channels=sorted(set(range(1,21))-cleared))
        elif all(c in cleared or len(negative[c])==len(cover) for c in range(1,21)):
            stopping_certificate=dict(method='seven_station_channel_cover')
        else:
            raise Incomplete('Stopping certificate is incomplete')
        if not 10<=len(cleared)<=16:raise Incomplete('Cleared count contradicts Q3 count bounds')
        exit_confirmed=client.exit()['exit_reason']=='user_exit'
    except (RuntimeError, ValueError, KeyError) as exc:
        failure=f'{type(exc).__name__}: {exc}'
    result=dict(status='complete' if failure is None and exit_confirmed else 'incomplete',failure=failure,
                exit_confirmed=exit_confirmed,cleared_channels=sorted(cleared),
                absent_channels=sorted(set(c for c in negative if len(negative[c])==len(cover))|
                    set((stopping_certificate or {}).get('inferred_absent_channels',[]))),
                negative_station_ids={str(c):sorted(v) for c,v in negative.items()},station_positions=cover,
                stopping_certificate=stopping_certificate,
                regions=regions,metrics=client.metrics(),modules=modules)
    if phase_decided:result['station_phase_rad']=station_phase
    event(dict(type='strategy_result',**result));return result
