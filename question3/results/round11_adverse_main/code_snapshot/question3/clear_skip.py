"""Conservative separating-halfplane proof that a radius-20 clear must fail.

If all feasible sources satisfy a.G <= b and (a.p-b)/||a|| > 20,
the entire closed clear disk is outside that halfplane. Failure is then certain.
This is sufficient only: an inconclusive test keeps the original action.
"""
import math
import numpy as np
from question1.solve import bearing_halfplanes


def constraints(first,bearing,second,reading,error_deg):
    return bearing_halfplanes([
        dict(x=first[0],y=first[1],bearing_deg=bearing),
        dict(x=second[0],y=second[1],bearing_deg=reading)],error_deg)


def failure_certificate(point,planes):
    if planes is None:return None
    A,b=planes;p=np.asarray(point,dtype=float)
    if not np.isfinite(p).all():return None
    norm=np.linalg.norm(A,axis=1)
    gaps=(A@p-b)/norm
    # Outward slack, never a tolerance allowing uncertain overlap to be removed.
    slack=1e-5+64*np.finfo(float).eps*(np.linalg.norm(p)+np.max(np.abs(b))+1)
    k=int(np.argmax(gaps))
    if not math.isfinite(float(gaps[k])) or gaps[k]<=20+slack:return None
    return dict(halfplane_index=k,separation_m=float(gaps[k]),slack_m=float(slack))
