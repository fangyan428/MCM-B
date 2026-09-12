"""Geometry for directional experiments, using only public positive bearings.

Distance screens and information gates do NOT certify directional reception.
"""
import math
import numpy as np
from question4.geometry import bearing_clip, estimate, EPS


def contains(poly, p):
    edges = np.roll(poly, -1, axis=0) - poly
    delta = np.asarray(p) - poly
    cross = edges[:, 0]*delta[:, 1] - edges[:, 1]*delta[:, 0]
    return bool(np.all(cross >= -EPS) or np.all(cross <= EPS))


def conditional_worthwhile(poly, point, fraction=.5, bins=16):
    """All possible *positive* output intervals must halve enclosing radius.

    Widening each interval by its half-width covers every serialized bearing.
    A no_signal outcome is explicitly excluded and conveys no spatial update.
    This is a contraction gate, not a probability or net time guarantee.
    """
    _, old = estimate(poly)
    if old < 20-1e-5:
        return False
    point = np.asarray(point)
    if contains(poly, point):
        low, high = 0., 360.
    else:
        ref = math.degrees(math.atan2(*(poly.mean(axis=0)-point)[::-1]))
        raw = np.degrees(np.arctan2((poly-point)[:, 1], (poly-point)[:, 0]))
        angles = ref+(raw-ref+180) % 360-180
        low, high = float(angles.min()-1.005), float(angles.max()+1.005)
    width = (high-low)/bins
    worst = 0.
    for k in range(bins):
        try:
            posterior = bearing_clip(poly, point, low+(k+.5)*width, 1.005+width/2)
        except RuntimeError:
            continue
        worst = max(worst, estimate(posterior)[1])
    return worst < max(20-1e-5, old*fraction)-1e-5


def proposals(poly, angle, current, mode):
    center, radius = estimate(poly)
    if mode == 'center':
        return [center]
    a = math.radians(angle)
    side = np.array([-math.sin(a), math.cos(a)])
    offset = math.sqrt(radius*20.)
    points = [center-offset*side, center+offset*side]
    return sorted(points, key=lambda p: math.dist(current, p))
