"""Continuous equal-disk coverage from public no-signal observations only."""
import itertools
import math
from functools import lru_cache
import numpy as np

@lru_cache(maxsize=8192)
def cover_radius(points):
    if not points:return math.inf
    p=np.asarray(points);candidates=[np.array([0.,0.])]
    for a in p:
        norm=float(np.linalg.norm(a))
        candidates.append(-1800*a/norm if norm else np.array([1800.,0.]))
    for a,b in itertools.combinations(p,2):
        n=b-a;norm=float(np.linalg.norm(n))
        if norm<1e-8:continue
        unit=n/norm;offset=float((b@b-a@a)/(2*norm))
        if abs(offset)<=1800:
            tangent=np.array([-unit[1],unit[0]])*math.sqrt(max(0.,1800**2-offset**2))
            candidates.extend([offset*unit+tangent,offset*unit-tangent])
    for a,b,c in itertools.combinations(p,3):
        A=2*np.stack([b-a,c-a])
        if abs(float(np.linalg.det(A)))<1e-8:continue
        v=np.linalg.solve(A,[b@b-a@a,c@c-a@a])
        if np.linalg.norm(v)<=1800+1e-8:candidates.append(v)
    v=np.asarray(candidates)
    return float(np.sqrt(((v[:,None,:]-p[None,:,:])**2).sum(axis=2)).min(axis=1).max())

def covered(points):
    pts=tuple(sorted(set(tuple(map(float,p)) for p in points)))
    return cover_radius(pts)<1000-1e-4

def verify_cover_boxes(points):
    """Independent conservative subdivision audit: no Voronoi formula reuse."""
    pts=np.asarray(points);stack=[(0.,0.,1800.,0)];leaves=0;visited=0;deepest=0
    while stack:
        x,y,h,depth=stack.pop();visited+=1;deepest=max(deepest,depth)
        if visited>2000000 or depth>30:raise AssertionError('Coverage interval audit unresolved')
        nearest=np.maximum(np.abs([x,y])-h,0)
        if nearest@nearest>1800**2:continue
        corners=np.array([[x-h,y-h],[x+h,y-h],[x+h,y+h],[x-h,y+h]])
        maximum=np.linalg.norm(corners[None,:,:]-pts[:,None,:],axis=2).max(axis=1)
        if float(maximum.min())<=1000-1e-8:
            leaves+=1;continue
        for sx,sy in itertools.product((-1,1),repeat=2):
            stack.append((x+sx*h/2,y+sy*h/2,h/2,depth+1))
    return dict(covered_boxes=leaves,visited_boxes=visited,max_depth=deepest)
