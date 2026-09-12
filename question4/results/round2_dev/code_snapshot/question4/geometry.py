"""Public geometry. No truth, emitter orientation, seed, or environment access."""
import math
from functools import lru_cache
import numpy as np
from scipy.spatial import Delaunay

EPS = 1e-7

def clip(poly, normal, bound):
    p = np.asarray(poly, float)
    if not len(p):
        return p
    d = p @ np.asarray(normal) - bound
    q = []
    for i in range(len(p)):
        j = (i + 1) % len(p)
        if d[i] <= 0:
            q.append(p[i])
        if (d[i] <= 0) != (d[j] <= 0):
            q.append(p[i] + (p[j] - p[i]) * d[i] / (d[i] - d[j]))
    return np.array(q).reshape(-1, 2)

def bearing_clip(poly, p, angle, error=1.005):
    for theta, sign in ((angle-error, 1), (angle+error, -1)):
        a = math.radians(theta)
        n = sign*np.array([math.sin(a), -math.cos(a)])
        poly = clip(poly, n, np.dot(n, p)+EPS)
    if not len(poly):
        raise RuntimeError('Empty bearing region: inconsistent readings')
    return poly

def first_region(p, angle, error=1.005):
    # Outer rectangle of the radius-1500 bearing sector, then outer domain polygon.
    a = math.radians(angle)
    u = np.array([math.cos(a), math.sin(a)])
    v = np.array([-u[1], u[0]])
    w = 1500*math.sin(math.radians(error))+EPS
    poly = np.array([np.array(p)+x*u+y*v for x,y in ((0,-w),(1500+EPS,-w),(1500+EPS,w),(0,w))])
    poly = bearing_clip(poly, p, angle, error)
    for t in np.arange(64)*2*math.pi/64:
        poly = clip(poly, [math.cos(t),math.sin(t)], 1800+EPS)
    if not len(poly):
        raise RuntimeError('Bearing outside public domain')
    return poly

def bbox(poly, angle):
    a = math.radians(angle)
    rot = np.array([[math.cos(a),-math.sin(a)],[math.sin(a),math.cos(a)]])
    local = np.asarray(poly)@rot
    lo, hi = local.min(axis=0)-EPS, local.max(axis=0)+EPS
    return lo, hi, rot

def optical_cover(poly, angle, start):
    lo, hi, rot = bbox(poly, angle)
    sizes = np.maximum(1,np.ceil((hi-lo)/28).astype(int))
    points = []
    for j in range(sizes[1]):
        for i in (range(sizes[0]) if j%2==0 else reversed(range(sizes[0]))):
            points.append((lo+(np.array([i+.5,j+.5])/sizes)*(hi-lo))@rot.T)
    if math.dist(start,points[-1]) < math.dist(start,points[0]):
        points.reverse()
    return points, float(np.linalg.norm((hi-lo)/sizes)/2)

def segment_distance(p, a, b):
    v = b-a
    t = np.clip(np.dot(p-a,v)/np.dot(v,v),0,1)
    return float(np.linalg.norm(p-a-t*v))

@lru_cache(maxsize=16)
def mesh(spacing=990.):
    if not 100 <= spacing < 1000:
        raise ValueError('Mesh sides must be strictly below minimum reception radius')
    n = math.ceil(2800/spacing)+2
    pts = np.array([(spacing*(i+j/2),spacing*math.sqrt(3)/2*j) for j in range(-n,n+1) for i in range(-n,n+1)])
    triang = Delaunay(pts)
    kept = []
    for tri in triang.simplices:
        v = pts[tri]
        if np.max(np.linalg.norm(v[:,None]-v[None,:],axis=2))>spacing+1e-5:
            continue
        signs = [np.linalg.det(np.stack([v[(i+1)%3]-v[i],-v[i]])) for i in range(3)]
        contains = min(signs)>=-EPS or max(signs)<=EPS
        dist = 0 if contains else min(segment_distance(np.zeros(2),v[i],v[(i+1)%3]) for i in range(3))
        if dist <= 1800+EPS:
            kept.append(tri)
    ids = sorted(set(int(i) for tri in kept for i in tri))
    remap = {old:new for new,old in enumerate(ids)}
    stations = pts[ids]
    triangles = np.array([[remap[int(i)] for i in tri] for tri in kept])
    return stations, triangles

def estimate(poly):
    # Midpoint of longest vertex pair; radius is certified against ALL vertices.
    d = np.sum((poly[:,None]-poly[None,:])**2,axis=2)
    i,j = np.unravel_index(np.argmax(d),d.shape)
    center = (poly[i]+poly[j])/2
    return center, float(np.linalg.norm(poly-center,axis=1).max())
