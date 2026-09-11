"""Optional D: one certified clear for a convex bearing-intersection polygon.
Enumerated centres are proposals; safety comes from rechecking EVERY vertex.
"""
import itertools
import numpy as np


def single_circle(vertices,margin=1e-5):
    v=np.asarray(vertices,dtype=float)
    if v.ndim!=2 or v.shape[1]!=2 or not len(v) or not np.isfinite(v).all():
        raise ValueError('Invalid convex polygon vertices')
    centres=list(v)
    centres.extend((a+b)/2 for a,b in itertools.combinations(v,2))
    for a,b,c in itertools.combinations(v,3):
        A=2*np.stack([b-a,c-a]);rhs=np.array([np.dot(b-a,b-a),np.dot(c-a,c-a)])
        if abs(np.linalg.det(A))<=1e-10:continue
        try:centres.append(a+np.linalg.solve(A,rhs))
        except np.linalg.LinAlgError:continue
    candidates=[(float(np.linalg.norm(v-p,axis=1).max()),tuple(map(float,p))) for p in centres if np.isfinite(p).all()]
    radius,centre=min(candidates)
    # A disk is convex: containing all vertices contains their entire convex hull.
    return (centre,radius) if radius<=20-margin else None
