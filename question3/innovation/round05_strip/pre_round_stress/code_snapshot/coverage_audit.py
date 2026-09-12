"""Post-run physical and continuous stop audit, never imported by policy."""
import json
import math
from .coverage import verify_cover_boxes

def audit(folder):
    data=json.loads((folder/'result.json').read_text())
    case=json.loads((folder/'evaluator_hidden_case.json').read_text())
    sources={s['channel']:s for s in case['sources']}
    requests={};done=set();cleared=set();negatives={c:set() for c in range(1,21)};directions={}
    position=(0.,0.);channel=1;virtual=0.;exited=False;actions=0
    for row in map(json.loads,(folder/'actions.jsonl').read_text().splitlines()):
        if row['type']=='request':requests[row['payload']['request_id']]=row
        if row['type']!='response' or not row['response'].get('accepted'):continue
        rid=row['request_id']
        if rid in done:continue
        done.add(rid);req=requests[rid];r=row['response'];b=req['payload'];path=req['path']
        if path in ('/measure','/clear'):
            p=(b['position']['x'],b['position']['y']);c=b['channel']
            assert all(math.isfinite(v) and abs(v)<=2000000 for v in p)
            virtual+=math.dist(position,p)/5;position=p
            s=sources.get(c);d=math.inf if s is None or c in cleared else math.dist(p,(s['x'],s['y']))
            if path=='/measure':
                virtual+=5+(c!=channel);channel=c
                expected='no_signal' if s is None or c in cleared or d>s['radius'] else ('near' if d<=5 else 'direction')
                assert r['measure_result']==expected
                if expected=='no_signal':negatives[c].add(p)
                if expected=='direction':
                    angle=math.degrees(math.atan2(s['y']-p[1],s['x']-p[0]))
                    error=1. if data['summary']['rounding']=='bounded' else 1.005
                    assert abs((r['svd_deg']-angle+180)%360-180)<=error+1e-8
                    if (p,c) in directions:assert directions[p,c]==r['svd_deg']
                    directions[p,c]=r['svd_deg']
            else:
                virtual+=3
                assert (r['clear_result']=='success')==(d<=20)
                if d<=20:cleared.add(c);virtual+=2
            actions+=1
        elif path=='/exit':exited=True
        assert abs(virtual-r['virtual_time_s'])<len(done)*1e-6+1e-4
    assert exited and cleared==set(sources)
    result=data['strategy'];assert result['status']=='complete' and set(result['cleared_channels'])==cleared
    cert=result['stopping_certificate'];checked={}
    if cert['method']=='source_count_upper_bound':
        assert len(cleared)==16
    elif cert['method']=='continuous_disk_union':
        for c in set(range(1,21))-cleared:
            pts=tuple(sorted(tuple(p) for p in cert['negative_positions'][str(c)]))
            assert set(pts)<=negatives[c]
            if pts not in checked:checked[pts]=verify_cover_boxes(pts)
    else:
        cover=set(map(tuple,result['station_positions']))
        for c in set(range(1,21))-cleared:assert cover<=negatives[c]
    return actions
