"""Offline public-domain halfplane-cover certificate. No case inputs."""
import argparse
import json
import math
from pathlib import Path
import numpy as np
from scipy.spatial import ConvexHull, QhullError

def generate(inner=7,outer=14,ri=995.,ro=1850.,depth_limit=12):
    points=np.array([(0.,0.)]+[(r*math.cos(2*math.pi*k/n),r*math.sin(2*math.pi*k/n))
        for n,r in ((inner,ri),(outer,ro)) for k in range(n)])
    leaves=[];failures=[];stack=[('',[-1800.,-1800.,1800.,1800.])]
    while stack:
        key,box=stack.pop();x0,y0,x1,y1=box
        dx=min(abs(x0),abs(x1)) if x0*x1>0 else 0
        dy=min(abs(y0),abs(y1)) if y0*y1>0 else 0
        if dx*dx+dy*dy>1800**2:
            leaves.append(dict(key=key,outside=True));continue
        v=np.array([(x0,y0),(x1,y0),(x1,y1),(x0,y1)])
        ids=np.where(np.linalg.norm(points[:,None]-v[None,:],axis=2).max(axis=1)<1000-1e-6)[0]
        if len(ids)>=3:
            try:
                hull=ConvexHull(points[ids]);h=hull.equations
                if np.max(v@h[:,:2].T+h[:,2])<1e-8:
                    leaves.append(dict(key=key,witnesses=ids[hull.vertices].tolist()));continue
            except QhullError:pass
        if len(key)==depth_limit:
            failures.append(dict(key=key,box=box));continue
        xm=(x0+x1)/2;ym=(y0+y1)/2
        for i,b in enumerate(((x0,y0,xm,ym),(xm,y0,x1,ym),(x0,ym,xm,y1),(xm,ym,x1,y1))):
            stack.append((key+str(i),b))
    return dict(stations=points.tolist(),leaves=leaves,failed_cells=failures,
                description='Each leaf lies inside convex hull of stations within 1000m of EVERY leaf point.')

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--negative21',action='store_true');args=p.parse_args()
    data=generate(8,12,990.,1870.) if args.negative21 else generate()
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(json.dumps(data,separators=(',',':')))
    print(dict(stations=len(data['stations']),leaves=len(data['leaves']),failed_cells=len(data['failed_cells'])))

if __name__=='__main__':main()
