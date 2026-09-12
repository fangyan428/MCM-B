"""Evaluator-only verification of the cell optical certificate."""
import math
import numpy as np
from question4.innovation.audit import _inside


def check_cells(case,events):
    checked=0
    for event in events:
        if event.get('event')!='optical_cells':continue
        p=np.array(event['vertices']);lo=np.array(event['low']);hi=np.array(event['high'])
        theta=math.radians(event['angle'])
        rot=np.array([[math.cos(theta),-math.sin(theta)],[math.sin(theta),math.cos(theta)]])
        local=p@rot;nx,ny=event['shape'];step=(hi-lo)/[nx,ny]
        assert 0<math.hypot(*step)/2<20
        assert np.all(local>=lo-1e-7) and np.all(local<=hi+1e-7)
        ids={tuple(c['index']) for c in event['cells']}
        assert len(ids)==len(event['cells'])
        # Independently determine cell/convex-polygon intersection with SAT.
        for j in range(ny):
            for i in range(nx):
                lower=lo+[i*step[0],j*step[1]];upper=lower+step
                corners=np.array([lower,[upper[0],lower[1]],upper,[lower[0],upper[1]]])
                edges=np.roll(local,-1,0)-local
                axes=[np.array([1.,0]),np.array([0.,1])]+[np.array([-e[1],e[0]]) for e in edges if np.linalg.norm(e)>1e-10]
                # A strictly positive overlap needs a retained cell; zero-area
                # shared boundaries are covered by their adjacent retained cell.
                overlap=all(min((local@a).max(),(corners@a).max())-max((local@a).min(),(corners@a).min())>1e-8 for a in axes)
                if overlap:assert (i,j) in ids,'Omitted intersecting cell'
        for cell in event['cells']:
            i,j=cell['index'];assert 0<=i<nx and 0<=j<ny
            center=(lo+(np.array([i,j])+.5)*step)@rot.T
            assert np.linalg.norm(center-cell['center'])<1e-6
            assert np.linalg.norm(np.asarray(cell['vertices'])-center,axis=1).max()<20
        s=next(s for s in case['sources'] if s['channel']==event['channel'])
        source=np.array([s['x'],s['y']]);assert _inside(p,source)
        assert min(np.linalg.norm(source-np.asarray(c['center'])) for c in event['cells'])<20
        checked+=1
    return {'passed':True,'checked_cell_covers':checked}
