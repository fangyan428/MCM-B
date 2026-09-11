"""Conservative separating-halfplane proof that a radius-20 clear must fail.

If all feasible sources satisfy a.G <= b and (a.p-b)/||a|| > 20,
the entire closed clear disk is outside that halfplane. Failure is then certain.
This is sufficient only: an inconclusive test keeps the original action.
"""
import math
from itertools import combinations
import numpy as np
from question1.solve import bearing_halfplanes


def constraints(first,bearing,second,reading,error_deg):
    return bearing_halfplanes([
        dict(x=first[0],y=first[1],bearing_deg=bearing),
        dict(x=second[0],y=second[1],bearing_deg=reading)],error_deg)


def failure_certificate(point,planes,combine=False):
    if planes is None:return None
    A,b=planes;p=np.asarray(point,dtype=float)
    if not np.isfinite(p).all():return None
    norm=np.linalg.norm(A,axis=1)
    gaps=(A@p-b)/norm
    # Outward slack, never a tolerance allowing uncertain overlap to be removed.
    slack=1e-5+64*np.finfo(float).eps*(np.linalg.norm(p)+np.max(np.abs(b))+1)
    k=int(np.argmax(gaps))
    if math.isfinite(float(gaps[k])) and gaps[k]>20+slack:
        return dict(halfplane_index=k,separation_m=float(gaps[k]),slack_m=float(slack))
    if not combine:return None
    # A pair's intersection proposes a normal. Only the final nonnegative
    # combination of original inequalities is trusted as the separating proof.
    for i,j in combinations(range(len(A)),2):
        matrix=A[[i,j]]
        if abs(np.linalg.det(matrix))<1e-10:continue
        vertex=np.linalg.solve(matrix,b[[i,j]])
        weights=np.linalg.solve(matrix.T,p-vertex)
        if not np.isfinite(weights).all() or np.any(weights<0) or weights.sum()<=0:continue
        weights=weights/weights.sum()
        normal=weights@matrix;length=float(np.linalg.norm(normal))
        if length<1e-8:continue
        bound=float(weights@b[[i,j]])
        separation=float((normal@p-bound)/length)
        # Near cancellation amplifies arithmetic error; inflate slack accordingly.
        margin=slack/length
        if not math.isfinite(separation) or separation<=20+margin:continue
        witness=np.zeros(len(A));witness[[i,j]]=weights
        return dict(halfplane_weights=witness.tolist(),separation_m=separation,slack_m=margin)
    return None


def radius_failure_certificate(point,first,second,mode):
    """Published containing disks only; never infer the source's actual radius."""
    circles=[]
    if mode in ('domain','both'):circles.append(('domain',(0.,0.),1800.))
    if mode in ('received','both'):
        circles.extend([('first_received',first,1500.),('second_received',second,1500.)])
    for name,centre,radius in circles:
        distance=math.dist(point,centre)
        slack=1e-5+64*np.finfo(float).eps*(math.hypot(*point)+math.hypot(*centre)+radius+1)
        if math.isfinite(distance) and distance>radius+20+slack:
            return dict(radius_prior=name,centre=list(centre),containing_radius_m=radius,
                        separation_m=distance-radius,slack_m=slack)
    return None
