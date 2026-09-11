"""Post-run oracle audit: evaluator only, NEVER called by the strategy."""
import argparse
import json
import math
import statistics
from pathlib import Path
import numpy as np
from question2.strategy import candidate
from .geometry import stations,station_cover_bound


def audit_folder(folder):
    case=json.loads((folder/'evaluator_hidden_case.json').read_text(encoding='utf-8'))
    result=json.loads((folder/'result.json').read_text(encoding='utf-8'))
    sources={s['channel']:s for s in case['sources']};requests={};cleared=set();negative={c:set() for c in range(1,21)}
    position=(0.,0.);channel=1;vt=0.;done=set();bearings={};measure_moves={};checks=0;outer_entry=None
    for line in (folder/'actions.jsonl').read_text(encoding='utf-8').splitlines():
        row=json.loads(line)
        if row['type']=='request':requests[row['payload']['request_id']]=row
        elif row['type']=='response' and row['response'].get('accepted') is True:
            rid=row['request_id']
            if rid in done:continue
            done.add(rid);req=requests[rid];b=req['payload'];r=row['response'];path=req['path']
            if path in ('/measure','/clear'):
                p=(b['position']['x'],b['position']['y']);c=b['channel'];move=math.dist(position,p)
                if path=='/measure' and req['phase']=='search' and math.hypot(*p)>1e-7 and outer_entry is None:
                    outer_entry=(position,p)
                vt+=move/5;position=p
                s=sources.get(c);distance=math.inf if s is None or c in cleared else math.hypot(s['x']-p[0],s['y']-p[1])
                if path=='/measure':
                    measure_moves[p,c]=move
                    vt+=5+(c!=channel);channel=c
                    expected='no_signal' if s is None or c in cleared or distance>s['radius'] else ('near' if distance<=5 else 'direction')
                    assert r['measure_result']==expected,(folder,expected,r)
                    if expected=='no_signal' and req['phase']=='search':negative[c].add(p)
                    if expected=='direction':
                        true=math.degrees(math.atan2(s['y']-p[1],s['x']-p[0]))
                        envelope=1. if result['summary']['rounding']=='bounded' else 1.005
                        assert abs((r['svd_deg']-true+180)%360-180)<=envelope+1e-9
                        key=(p,c)
                        if key in bearings:assert bearings[key]==r['svd_deg']
                        bearings[key]=r['svd_deg']
                else:
                    vt+=3
                    if distance<=20:
                        assert r['clear_result']=='success';cleared.add(c);vt+=2
                    else:assert r['clear_result']=='no_target_in_range'
                checks+=1
            assert abs(vt-r['virtual_time_s'])<=len(done)*1e-6+1e-4
    strategy=result['strategy']
    assert strategy['status']=='complete' and strategy['exit_confirmed']
    assert set(strategy['cleared_channels'])==cleared
    cover={tuple(s) for s in strategy['station_positions']}
    assert len(cover)==7
    radius=math.dist((0,0),strategy['station_positions'][1])
    assert station_cover_bound(radius)<1000
    phase=strategy.get('station_phase_rad',0.)
    assert math.isfinite(phase)
    assert np.allclose(strategy['station_positions'],stations(radius,phase),atol=1e-7,rtol=0)
    phase_events=[e for e in map(json.loads,(folder/'strategy.jsonl').read_text().splitlines()) if e['type']=='ring_phase_selected']
    assert len(phase_events)==(1 if 'station_phase_rad' in strategy else 0)
    if phase_events:
        e=phase_events[0];i=e['station_id'];assert 1<=i<=6 and e['visited_before']==[0]
        assert e['phase_rad']==phase and outer_entry is not None
        assert tuple(e['position'])==outer_entry[0] and tuple(e['new_station'])==outer_entry[1]
        assert np.allclose(e['old_station'],stations(radius)[i],atol=1e-7,rtol=0)
        assert tuple(strategy['station_positions'][i])==outer_entry[1]
        shortest=abs(math.hypot(*outer_entry[0])-radius)
        assert abs(math.dist(*outer_entry)-shortest)<1e-7
        saved=(math.dist(outer_entry[0],e['old_station'])-math.dist(*outer_entry))/5
        assert saved>=-1e-7 and abs(saved-e['local_movement_saved_s'])<1e-7
    certificate=strategy.get('stopping_certificate') or {}
    if certificate.get('method')=='source_count_upper_bound':
        # Count accepted SUCCESS feedback on distinct channels, never attempts or detections.
        assert certificate['source_upper_bound']==16
        assert len(certificate['successful_channels'])==16
        assert len(cleared)==16 and set(certificate['successful_channels'])==cleared
        assert set(certificate['inferred_absent_channels'])==set(range(1,21))-cleared
        assert len(sources)<=16 # Evaluator checks the published model's applicability.
    else:
        for c in range(1,21):assert c in cleared or cover<=negative[c],(folder,c)
    assert cleared==set(sources)
    for region in strategy['regions']:
        selection=region.get('selection',{})
        if selection.get('mode') in ('shared_certified','opportunistic_current'):
            first=tuple(region['first_position']);second=tuple(region['second_position']);c=region['channel']
            angle=math.radians(bearings[first,c]);dx=second[0]-first[0];dy=second[1]-first[1]
            offset=(dx*math.cos(angle)+dy*math.sin(angle),-dx*math.sin(angle)+dy*math.cos(angle))
            assert np.allclose(offset,selection['offset'],atol=1e-7,rtol=0)
            assert candidate(offset,selection['min_angle_deg'],selection['error_deg'])
            assert (second,c) in bearings
            if selection['mode']=='opportunistic_current':assert measure_moves[second,c]==0
        if 'vertices' not in region:continue
        g=np.array([sources[region['channel']]['x'],sources[region['channel']]['y']]);v=np.array(region['vertices'])
        edges=np.roll(v,-1,axis=0)-v;rel=g-v
        cross=edges[:,0]*rel[:,1]-edges[:,1]*rel[:,0]
        assert np.all(cross>=-1e-5) or np.all(cross<=1e-5)
        assert region['covering_radius']<20
        if 'single_circle_centre' in region:
            centre=np.array(region['single_circle_centre'])
            assert np.linalg.norm(v-centre,axis=1).max()<=20-1e-5+1e-9
            assert np.linalg.norm(g-centre)<=20
            assert region['planned_clear_calls']==1
    # Independently recompute each omitted action's separating witness from accepted bearings.
    from question1.solve import bearing_halfplanes
    regions={r['channel']:r for r in strategy['regions']}
    for line in (folder/'strategy.jsonl').read_text(encoding='utf-8').splitlines():
        event=json.loads(line)
        if event['type']!='certified_clear_skip':continue
        c=event['channel'];region=regions[c];first=tuple(region['first_position']);second=tuple(region['second_position'])
        if 'radius_prior' in event:
            expected={'domain':((0.,0.),1800.),'first_received':(first,1500.),'second_received':(second,1500.)}
            centre,radius=expected[event['radius_prior']]
            assert tuple(event['centre'])==centre and event['containing_radius_m']==radius
            if event['radius_prior']!='domain':assert (centre,c) in bearings
            gap=math.dist(event['point'],centre)-radius
            assert event['slack_m']>=1e-5 and gap>20+event['slack_m']
            assert abs(gap-event['separation_m'])<1e-8
            g=(sources[c]['x'],sources[c]['y'])
            assert math.dist(g,centre)<=radius+1e-7 and math.dist(g,event['point'])>20
            continue
        assert event['error_deg']>=(1. if result['summary']['rounding']=='bounded' else 1.005)
        A,b=bearing_halfplanes([dict(x=p[0],y=p[1],bearing_deg=bearings[p,c]) for p in [first,second]],event['error_deg'])
        p=np.asarray(event['point'])
        if 'halfplane_weights' in event:
            weights=np.asarray(event['halfplane_weights'])
            assert weights.shape==(len(A),) and np.isfinite(weights).all() and np.all(weights>=0)
            assert abs(float(weights.sum())-1)<1e-12
            normal=weights@A;bound=float(weights@b);length=float(np.linalg.norm(normal))
            assert length>=1e-8
            gap=float((normal@p-bound)/length)
            assert event['slack_m']>=1e-5/length
        else:
            k=event['halfplane_index'];gap=float((A[k]@p-b[k])/np.linalg.norm(A[k]))
        assert event['slack_m']>=1e-5 and gap>20+event['slack_m']
        assert abs(gap-event['separation_m'])<1e-8
        assert math.dist(p,(sources[c]['x'],sources[c]['y']))>20
    return checks


def main():
    p=argparse.ArgumentParser();p.add_argument('folder');args=p.parse_args();root=Path(args.folder)
    summary=json.loads((root/'summary.json').read_text(encoding='utf-8'));rows=summary['cases']
    checks=sum(audit_folder(root/r['case_id']) for r in rows)
    aggregate=dict(kind='SELF_POST_RUN_AUDIT',runs=len(rows),actions_checked=checks,
                   all_stopping_certificates_valid=True,all_physics_and_time_checks_passed=True,
                   mean_virtual_s=statistics.mean(r['metrics']['virtual_time_s'] for r in rows),
                   mean_case_average_per_clear_s=statistics.mean(r['average_virtual_per_cleared'] for r in rows),
                   pooled_virtual_per_clear_s=sum(r['metrics']['virtual_time_s'] for r in rows)/sum(r['cleared'] for r in rows),
                   total_cleared_over_runs=sum(r['cleared'] for r in rows),
                   worst_total_case=max(rows,key=lambda r:r['metrics']['virtual_time_s']),
                   worst_per_clear_case=max(rows,key=lambda r:r['average_virtual_per_cleared']),
                   most_failed_clear_case=max(rows,key=lambda r:r['metrics']['counts']['clear_failure']),
                   component_means={k:statistics.mean(r['metrics']['components'][k] for r in rows) for k in rows[0]['metrics']['components']},
                   min_wall_s=min(r['elapsed_wall_s'] for r in rows),max_wall_s=max(r['elapsed_wall_s'] for r in rows))
    (root/'audit.json').write_text(json.dumps(aggregate,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in aggregate.items() if not isinstance(v,dict)},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
