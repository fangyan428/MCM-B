"""Published-domain range bound and sufficient second-bearing certificate.

No source truth. The 31x3x3 diameter proxy ranks candidates only; analytic
inequalities certify the continuous sector. Used after task selection only.
"""
from functools import lru_cache
import math
import numpy as np
from question2.strategy import diameters,to_world
from .current_point import local_offset


def range_upper(first,bearing,error_deg):
    rho=math.hypot(*first)
    if not math.isfinite(rho+bearing+error_deg) or not 0<error_deg<45:
        raise ValueError('Invalid first-bearing geometry')
    if rho==0 or rho>1800:return 1500
    delta=math.radians(error_deg)
    beta=(math.atan2(first[1],first[0])-math.radians(bearing)+math.pi)%(2*math.pi)-math.pi
    m=rho*(-1. if abs(beta)+delta>=math.pi else min(math.cos(beta-delta),math.cos(beta+delta)))
    exact=-m+math.sqrt(max(0.,m*m+1800**2-rho*rho))
    upper=min(1500,math.ceil(exact+1e-5))
    return upper if upper>5 else 1500


def certified(offset,upper,error_deg,min_angle_deg):
    a,b=offset
    if not all(map(math.isfinite,[a,b,upper,error_deg,min_angle_deg])):return False
    if a<0 or not 5<upper<=1500 or not 0<error_deg<45 or not 4*error_deg<min_angle_deg<90:return False
    d=math.radians(error_deg);h=a*math.cos(d)-abs(b)*math.sin(d);n=a*a+b*b
    d5=n+25-10*h;du=n+upper**2-2*upper*h
    # R >= max(1000,r). On [1000,U], n-2rh <= 0 follows at r=1000.
    receives=d5<=1000**2-1e-4 and (du<=1000**2-1e-4 if upper<=1000 else n<=2000*h-1e-4)
    cross=abs(b)*math.cos(d)-a*math.sin(d)
    return bool(receives and cross>5+1e-7 and cross>=math.sqrt(max(d5,du))*math.sin(math.radians(min_angle_deg))+1e-7)


@lru_cache(maxsize=4096)
def proxy(offset,upper,error_deg,min_angle_deg):
    if not certified(offset,upper,error_deg,min_angle_deg):return None
    d=math.radians(error_deg)
    r,a,e=np.meshgrid(np.linspace(5.001,upper,31),np.linspace(-d,d,3),np.linspace(-d,d,3),indexing='ij')
    g=np.column_stack([(r*np.cos(a)).ravel(),(r*np.sin(a)).ravel()])
    diameter=float(diameters(offset,g,e.ravel(),error_deg).max())
    x,y=offset;h=x*math.cos(d)-abs(y)*math.sin(d);n=x*x+y*y
    maximum=math.sqrt(max(n+25-10*h,n+upper**2-2*upper*h))
    cells=math.ceil(diameter/28)*math.ceil(2*upper*math.sin(d)/28)
    return dict(offset=offset,sampled_worst_diameter=diameter,max_source_distance=maximum,
                proxy_cells=cells,continuation_proxy_s=maximum/5+8.6*cells)


def choose(first,bearing,current,config,base_catalog,upper):
    original={tuple(row['offset']) for row in base_catalog}
    offsets=original|{(x*upper/1500,y*upper/1500) for x,y in original}
    best=None
    for offset in sorted(offsets):
        row=proxy(offset,upper,config['error_deg'],config['min_angle_deg'])
        if row is None:continue
        q=tuple(to_world(offset,first,bearing));score=math.dist(current,q)/5+5+row['continuation_proxy_s']
        if best is None or (score,offset)<best[0]:best=((score,offset),q,row)
    if best is None:raise RuntimeError('No domain-certified candidate including original catalog')
    metadata=dict(source_range_upper_m=upper,range_prior='published_domain_1800',
                  error_deg=config['error_deg'],min_angle_deg=config['min_angle_deg'])
    opportunity=config.get('second_point_opportunity','off')
    if opportunity!='off':
        row=proxy(local_offset(first,bearing,current),upper,config['error_deg'],config['min_angle_deg'])
        if row is not None:
            score=5+row['continuation_proxy_s']
            if opportunity=='current_if_certified' or score<best[0][0]-1e-8:
                return tuple(current),dict(mode='domain_current',score_s=score,**row,**metadata,
                    selection_rule=opportunity,catalog_score_s=best[0][0],catalog_point=best[1])
    return best[1],dict(mode='domain_cost_proxy',score_s=best[0][0],**best[2],**metadata)
