"""Conservative convex sets from public bounded bearings. No environment access."""
import itertools
import math
import numpy as np

SLACK = 1e-7

def clip(poly, normal, bound):
    normal = np.asarray(normal, float)
    result = []
    for a,b in zip(poly, np.roll(poly,-1,axis=0)):
        da, db = float(normal@a-bound), float(normal@b-bound)
        if da <= 0:
            result.append(a)
        if (da <= 0) != (db <= 0):
            result.append(a + (b-a)*(da/(da-db)))
    if not result:
        raise RuntimeError('Empty conservative feasible polygon')
    return np.asarray(result)

def disk(poly, centre, radius):
    # Tangent halfplanes OUTSIDE the disk; never use an inscribed approximation.
    centre = np.asarray(centre)
    for k in range(32):
        t = 2*math.pi*k/32
        n = np.array([math.cos(t),math.sin(t)])
        poly = clip(poly,n,float(n@centre+radius+SLACK))
    return poly

def wedge(poly, point, bearing, error=1.005):
    for sign in (-1,1):
        t = math.radians(bearing+sign*error)
        n = np.array([-sign*math.sin(t),sign*math.cos(t)])
        poly = clip(poly,n,float(n@np.asarray(point)+SLACK))
    return poly

def initial(point, bearing, error=1.005):
    poly = np.array([[-1800.,-1800.],[1800.,-1800.],[1800.,1800.],[-1800.,1800.]])
    poly = wedge(poly,point,bearing,error)
    return disk(disk(poly,(0,0),1800),point,1500)

def bbox(poly, bearing):
    t = math.radians(bearing)
    rot = np.array([[math.cos(t),-math.sin(t)],[math.sin(t),math.cos(t)]])
    local = poly@rot
    lo,hi = local.min(axis=0)-SLACK,local.max(axis=0)+SLACK
    centre = ((lo+hi)/2)@rot.T
    radius = float(np.linalg.norm(poly-centre,axis=1).max()+SLACK)
    return centre,radius,lo,hi,rot

def enclosing(poly):
    # Small convex polygons: enumerate every support pair/triple, then verify all vertices.
    candidates = [p for p in poly]
    candidates += [(a+b)/2 for a,b in itertools.combinations(poly,2)]
    for a,b,c in itertools.combinations(poly,3):
        u,v = b-a,c-a
        A=2*np.stack([u,v])
        if abs(float(np.linalg.det(A))) < 1e-9:
            continue
        p=a+np.linalg.solve(A,[u@u,v@v])
        if np.isfinite(p).all():
            candidates.append(p)
    best=min((float(np.linalg.norm(poly-p,axis=1).max()),tuple(p)) for p in candidates)
    return np.array(best[1]),best[0]+SLACK

def grid(poly,bearing):
    _,_,lo,hi,rot=bbox(poly,bearing)
    sizes=np.maximum(1,np.ceil((hi-lo)/28).astype(int))
    if int(np.prod(sizes))>2000:
        raise RuntimeError('Optical finite fallback guard')
    for j in range(sizes[1]):
        for i in (range(sizes[0]) if j%2==0 else reversed(range(sizes[0]))):
            yield (lo+np.array([i+.5,j+.5])*(hi-lo)/sizes)@rot.T

def contains(poly,p,tol=1e-4):
    e=np.roll(poly,-1,axis=0)-poly
    v=np.asarray(p)-poly
    cross=e[:,0]*v[:,1]-e[:,1]*v[:,0]
    return bool(np.all(cross>=-tol) or np.all(cross<=tol))

def parallax_point(poly,bearing,current):
    """Geometry-scaled parallax: balance cross-track detour and angular uncertainty.

    Baseline scale derives from r*sin(delta), with 20m as the physical accuracy target.
    No source-distance or error-mode oracle. Candidates require a full vertex reception check.
    """
    centre,radius,*_=bbox(poly,bearing)
    t=math.radians(bearing);side=np.array([-math.sin(t),math.cos(t)])
    # sqrt(range * optical radius) gives a scale between optical accuracy and range.
    offset=math.sqrt(radius*20)
    candidates=[centre+sign*offset*side for sign in (-1,1)]
    valid=[p for p in candidates if np.linalg.norm(poly-p,axis=1).max()<1000-1e-5]
    if not valid:return centre,radius
    p=min(valid,key=lambda p:math.dist(current,p))
    return p,float(np.linalg.norm(poly-p,axis=1).max()+SLACK)
