"""Deterministic free-end open tour, replanned after each public action batch."""
import numpy as np

def tour(start,points):
    p=np.vstack([start,points]);d=np.linalg.norm(p[:,None]-p[None,:],axis=2)
    remaining=set(range(1,len(p)));order=[0]
    while remaining:
        j=min(remaining,key=lambda j:(d[order[-1],j],j));order.append(j);remaining.remove(j)
    # Reverse a segment, including the free endpoint. No return-to-origin penalty.
    for _ in range(50):
        best=0.;move=None
        for i in range(1,len(order)-1):
            for j in range(i+1,len(order)):
                delta=d[order[i-1],order[j]]-d[order[i-1],order[i]]
                if j+1<len(order):delta+=d[order[i],order[j+1]]-d[order[j],order[j+1]]
                if delta<best-1e-8:best=delta;move=(i,j)
        if move is None:break
        i,j=move;order[i:j+1]=reversed(order[i:j+1])
    return [i-1 for i in order[1:]]
