"""Current-position opportunity: analytic eligibility, unchanged A cost proxy.
No source or error-field truth; the sampled diameter is a score, not a certificate.
"""
import math
from functools import lru_cache
import numpy as np
from question2.strategy import candidate,diameters


def local_offset(first,bearing,current):
    angle=math.radians(bearing);dx=current[0]-first[0];dy=current[1]-first[1]
    return (dx*math.cos(angle)+dy*math.sin(angle),-dx*math.sin(angle)+dy*math.cos(angle))


@lru_cache(maxsize=2048)
def current_proxy(offset,error_deg,min_angle_deg):
    if not candidate(offset,min_angle_deg,error_deg):return None
    delta=math.radians(error_deg)
    r,a,e=np.meshgrid(np.linspace(5.001,1500,31),np.linspace(-delta,delta,3),
                      np.linspace(-delta,delta,3),indexing='ij')
    g=np.column_stack([(r*np.cos(a)).ravel(),(r*np.sin(a)).ravel()])
    diameter=float(diameters(offset,g,e.ravel(),error_deg).max())
    x,y=offset;h=x*math.cos(delta)-abs(y)*math.sin(delta)
    max_range=math.sqrt(max(x*x+y*y+25-10*h,x*x+y*y+1500**2-3000*h))
    cells=math.ceil(diameter/28)*math.ceil(2*1500*math.sin(delta)/28)
    continuation=max_range/5+8.6*cells
    return dict(offset=offset,sampled_worst_diameter=diameter,max_source_distance=max_range,
                proxy_cells=cells,continuation_proxy_s=continuation)
