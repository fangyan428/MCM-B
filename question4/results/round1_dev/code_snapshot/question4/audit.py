"""Independent post-run physical replay, time accounting, and stop-certificate audit."""
import math
from collections import Counter
import numpy as np
from .geometry import segment_distance

def audit(case,records,result):
    sources={s['channel']:s for s in case['sources']}; cleared=set(); measured={}
    requests={}; p=(0.,0.);channel=1;vt=0.;n=0;exited=False
    for row in records:
        if row['type']=='request':
            requests[row['payload']['request_id']]=row
        if row['type']!='response' or row.get('attempt',0)>0:
            continue
        req=requests[row['request_id']]; b=req['payload'];path=req['path'];r=row['response']
        assert row['http_status']==200 and r['accepted'] is True
        n+=1
        if path=='/exit':exited=True
        if path in ('/measure','/clear'):
            q=(b['position']['x'],b['position']['y']);ch=b['channel']
            vt+=math.dist(p,q)/5
            s=sources.get(ch);d=math.inf if s is None or ch in cleared else math.dist(q,(s['x'],s['y']))
            if path=='/measure':
                vt+=5+(ch!=channel);channel=ch
                axis=None if s is None else s.get('direction_deg')
                angle=0 if s is None else math.degrees(math.atan2(q[1]-s['y'],q[0]-s['x']))
                visible=axis is None or abs((angle-axis+180)%360-180)<=90+1e-9 or d<1e-10
                expected='no_signal' if s is None or ch in cleared or d>s['radius'] or not visible else 'near' if d<=5 else 'direction'
                assert r['measure_result']==expected,(expected,r)
                if expected=='direction':
                    true=math.degrees(math.atan2(s['y']-q[1],s['x']-q[0]))
                    assert abs((r['svd_deg']-true+180)%360-180)<=1.0050001
                measured.setdefault(ch,[]).append(q)
            else:
                expected='success' if d<=20 else 'no_target_in_range'
                assert r['clear_result']==expected
                vt+=5 if d<=20 else 3
                if d<=20:cleared.add(ch)
            p=q
        assert abs(vt-r['virtual_time_s'])<n*1e-6+1e-5
    assert exited and result['status']=='complete'
    assert cleared==set(sources), 'False completion against hidden truth'
    assert cleared==set(result['cleared'])
    cert=result['stop_certificate']
    if cert['kind']=='count16':
        assert len(cleared)==16
    else:
        points=np.array(cert['stations']);triangles=cert['triangles']; edges=Counter()
        contains_origin=False
        for tri in triangles:
            v=points[tri]
            assert np.linalg.norm(v[:,None]-v[None,:],axis=2).max()<1000
            signs=[np.linalg.det(np.stack([v[(i+1)%3]-v[i],-v[i]])) for i in range(3)]
            contains_origin |= min(signs)>=-1e-6 or max(signs)<=1e-6
            for i in range(3):edges[tuple(sorted((tri[i],tri[(i+1)%3])))]+=1
        assert contains_origin
        for (a,b),count in edges.items():
            assert count<=2
            if count==1:assert segment_distance(np.zeros(2),points[a],points[b])>=1800-1e-5
        for ch in set(range(1,21))-cleared:
            actual=set(measured.get(ch,[]))
            assert all(tuple(p) in actual for p in points),'Unscanned absent channel'
    return dict(passed=True,accepted_actions=n,cleared=len(cleared),virtual_time_s=vt)
