"""Public geometry only; reuse Q1 and Q2, no simulator imports."""
import math
import numpy as np
from question1.solve import solve
from question2.strategy import candidate, to_world


def stations():
    return [(0.,0.)]+[(1500*math.cos(k*math.pi/3),1500*math.sin(k*math.pi/3)) for k in range(6)]


def station_cover_bound():
    # Centre covers radius <=900. Remaining annulus: nearest ring angle <=30deg.
    return max(900.,*(math.sqrt(r*r+1500**2-2*r*1500*math.cos(math.pi/6)) for r in [900,1800]))


def second_point(first, bearing, offset, error_deg, min_angle):
    if not candidate(offset,min_angle,error_deg):
        raise ValueError('Second offset lacks analytic reception/angle certificate')
    if min_angle <= 4*error_deg:
        raise ValueError('Angle margin insufficient for bounded two-wedge intersection')
    return tuple(to_world(offset,first,bearing))


def optical_plan(first, bearing, second, reading, error_deg, cell_m, max_points):
    """Cover an inflated rotated bounding box by <=28m cells. No hidden G.

    Cells have diagonal/2 <20m. Testing every centre guarantees a hit if G is in P.
    """
    if not 0 < cell_m < 20*math.sqrt(2):
        raise ValueError('Optical cells must fit strictly inside a radius-20 circle')
    result=solve([dict(x=first[0],y=first[1],bearing_deg=bearing),
                  dict(x=second[0],y=second[1],bearing_deg=reading)],error_deg)
    if result['status']!='bounded':
        raise RuntimeError('Invalid localization region: '+result['status'])
    vertices=np.array(result['vertices'])
    a=math.radians(bearing)
    rot=np.array([[math.cos(a),-math.sin(a)],[math.sin(a),math.cos(a)]])
    local=(vertices-np.array(first))@rot
    lo=local.min(axis=0)-1e-5;hi=local.max(axis=0)+1e-5
    sizes=np.maximum(1,np.ceil((hi-lo)/cell_m).astype(int))
    n=int(np.prod(sizes))
    if n>max_points:
        raise RuntimeError(f'Optical plan exceeds configured guard: {n}')
    points=[]
    for j in range(sizes[1]):
        cols=range(sizes[0]) if j%2==0 else reversed(range(sizes[0]))
        for i in cols:
            p=lo+(np.array([i+.5,j+.5])/sizes)*(hi-lo)
            points.append(tuple(np.array(first)+rot@p))
    certificate=dict(diameter=result['diameter'],vertices=result['vertices'],
                     bbox_widths=(hi-lo).tolist(),planned_clear_calls=n,
                     covering_radius=float(np.linalg.norm((hi-lo)/sizes)/2))
    return points,certificate
