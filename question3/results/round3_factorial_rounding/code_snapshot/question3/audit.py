"""Post-run oracle audit: evaluator only, NEVER called by the strategy."""
import argparse
import json
import math
import statistics
from pathlib import Path
import numpy as np
from question2.strategy import candidate


def audit_folder(folder):
    case=json.loads((folder/'evaluator_hidden_case.json').read_text(encoding='utf-8'))
    result=json.loads((folder/'result.json').read_text(encoding='utf-8'))
    sources={s['channel']:s for s in case['sources']};requests={};cleared=set();negative={c:set() for c in range(1,21)}
    position=(0.,0.);channel=1;vt=0.;done=set();bearings={};checks=0
    for line in (folder/'actions.jsonl').read_text(encoding='utf-8').splitlines():
        row=json.loads(line)
        if row['type']=='request':requests[row['payload']['request_id']]=row
        elif row['type']=='response' and row['response'].get('accepted') is True:
            rid=row['request_id']
            if rid in done:continue
            done.add(rid);req=requests[rid];b=req['payload'];r=row['response'];path=req['path']
            if path in ('/measure','/clear'):
                p=(b['position']['x'],b['position']['y']);c=b['channel'];vt+=math.dist(position,p)/5;position=p
                s=sources.get(c);distance=math.inf if s is None or c in cleared else math.hypot(s['x']-p[0],s['y']-p[1])
                if path=='/measure':
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
    cover={tuple(s) for s in strategy['station_positions']}
    assert len(cover)==7
    for c in range(1,21):assert c in cleared or cover<=negative[c],(folder,c)
    assert cleared==set(sources)
    for region in strategy['regions']:
        selection=region.get('selection',{})
        if selection.get('mode')=='shared_certified':
            first=tuple(region['first_position']);second=tuple(region['second_position']);c=region['channel']
            angle=math.radians(bearings[first,c]);dx=second[0]-first[0];dy=second[1]-first[1]
            offset=(dx*math.cos(angle)+dy*math.sin(angle),-dx*math.sin(angle)+dy*math.cos(angle))
            assert np.allclose(offset,selection['offset'],atol=1e-7,rtol=0)
            assert candidate(offset,selection['min_angle_deg'],selection['error_deg'])
            assert (second,c) in bearings
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
