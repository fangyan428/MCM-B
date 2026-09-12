"""Deterministic free-end open tour, replanned after each public action batch."""
import numpy as np

def tour(start,points,source_weights=None,station_flags=None,relocate=False):
    p=np.vstack([start,points]);d=np.linalg.norm(p[:,None]-p[None,:],axis=2)
    remaining=set(range(1,len(p)));order=[0]
    while remaining:
        j=min(remaining,key=lambda j:(d[order[-1],j],j));order.append(j);remaining.remove(j)
    # Reverse a segment, including the free endpoint. No return-to-origin penalty.
    for _ in range(50):
        weights=np.array([0.]+list(source_weights or [0.]*len(points)))[order]
        flags=np.array([0.]+list(station_flags or [0.]*len(points)))[order]
        sw=np.r_[0.,np.cumsum(weights)];sf=np.r_[0.,np.cumsum(flags)]
        inv=np.r_[0.,np.cumsum(weights*sf[:-1])]
        best=0.;move=None
        for i in range(1,len(order)-1):
            for j in range(i+1,len(order)):
                delta=d[order[i-1],order[j]]-d[order[i-1],order[i]]
                if j+1<len(order):delta+=d[order[i],order[j+1]]-d[order[j],order[j+1]]
                # Clearing a known source saves future station detections.
                inversion=(inv[j+1]-inv[i])-sf[i]*(sw[j+1]-sw[i])
                delta+=5*((sf[j+1]-sf[i])*(sw[j+1]-sw[i])-2*inversion)
                if delta<best-1e-8:best=delta;move=(i,j)
        if move is None:break
        i,j=move;order[i:j+1]=reversed(order[i:j+1])
    if relocate:
        def cost(o):
            distance=sum(d[a,b] for a,b in zip(o,o[1:]))
            weights0=[0.]+list(source_weights or [0.]*len(points))
            flags0=[0.]+list(station_flags or [0.]*len(points))
            seen=0.;penalty=0.
            for i in o:
                penalty+=weights0[i]*seen;seen+=flags0[i]
            return distance+5*penalty
        for _ in range(10):
            best=cost(order);candidate=None
            for i in range(1,len(order)):
                short=order[:i]+order[i+1:]
                for j in range(1,len(order)):
                    if i==j:continue
                    proposal=short[:j]+[order[i]]+short[j:];value=cost(proposal)
                    if value<best-1e-8:best=value;candidate=proposal
            if candidate is None:break
            order=candidate
    return [i-1 for i in order[1:]]
