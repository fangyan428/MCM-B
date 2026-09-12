"""Independent post-run physical replay, time accounting, and stop-certificate audit."""
import math
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from collections import Counter
import numpy as np
from .geometry import segment_distance

@lru_cache(maxsize=4)
def check_cover(contents):
    data=json.loads(contents);assert not data['failed_cells']
    points=np.array(data['stations']);leaves={r['key']:r for r in data['leaves']}
    assert len(leaves)==len(data['leaves'])
    nodes=set()
    for key in leaves:
        assert set(key)<=set('0123')
        nodes.update(key[:i] for i in range(len(key)))
    assert not (nodes & leaves.keys())
    for key in nodes:assert all(key+str(i) in nodes or key+str(i) in leaves for i in range(4))
    assert '' in nodes or '' in leaves
    for key,row in leaves.items():
        x0,y0,x1,y1=-1800.,-1800.,1800.,1800.
        for digit in key:
            xm=(x0+x1)/2;ym=(y0+y1)/2
            x0,y0,x1,y1=((x0,y0,xm,ym),(xm,y0,x1,ym),(x0,ym,xm,y1),(xm,ym,x1,y1))[int(digit)]
        if row.get('outside'):
            dx=max(x0,0,-x1);dy=max(y0,0,-y1)
            assert dx*dx+dy*dy>1800**2
            continue
        corners=np.array([(x0,y0),(x1,y0),(x1,y1),(x0,y1)])
        hull=points[row['witnesses']];assert len(hull)>=3
        assert len(set(row['witnesses']))==len(hull)
        q=np.roll(hull,-1,axis=0)
        assert np.sum(hull[:,0]*q[:,1]-hull[:,1]*q[:,0])>1e-6
        assert np.linalg.norm(hull[:,None]-corners[None,:],axis=2).max()<1000
        for i in range(len(hull)):
            a=hull[i];edge=hull[(i+1)%len(hull)]-a
            cross=edge[0]*(corners[:,1]-a[1])-edge[1]*(corners[:,0]-a[0])
            assert cross.min()>=-1e-7
    return points

def audit(case,records,result):
    sources={s['channel']:s for s in case['sources']}; cleared=set(); measured={}
    requests={}; executed=set();p=(0.,0.);channel=1;vt=0.;n=0;exited=False
    for row in records:
        if row['type']=='request':
            requests[row['payload']['request_id']]=row
        if row['type']!='response' or row['request_id'] in executed:
            continue
        req=requests[row['request_id']]; b=req['payload'];path=req['path'];r=row['response']
        assert row['http_status']==200 and r['accepted'] is True
        executed.add(row['request_id'])
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
        if cert['kind']=='cell_halfplane_cover':
            contents=(Path(__file__).with_name('certificates')/'compact22.json').read_bytes()
            assert hashlib.sha256(contents).hexdigest()==cert['cover_sha256']
            assert np.array_equal(points,check_cover(contents))
        contains_origin=False
        assert len({tuple(sorted(t)) for t in triangles})==len(triangles)
        for tri in triangles:
            v=points[tri]
            assert np.linalg.norm(v[:,None]-v[None,:],axis=2).max()<1000
            signs=[np.linalg.det(np.stack([v[(i+1)%3]-v[i],-v[i]])) for i in range(3)]
            contains_origin |= min(signs)>=-1e-6 or max(signs)<=1e-6
            for i in range(3):edges[tuple(sorted((tri[i],tri[(i+1)%3])))]+=1
        assert contains_origin or cert['kind']=='cell_halfplane_cover'
        for (a,b),count in edges.items():
            assert count<=2
            if count==1:assert segment_distance(np.zeros(2),points[a],points[b])>=1800-1e-5
        for ch in set(range(1,21))-cleared:
            actual=set(measured.get(ch,[]))
            assert all(tuple(p) in actual for p in points),'Unscanned absent channel'
    return dict(passed=True,accepted_actions=n,cleared=len(cleared),virtual_time_s=vt)
