"""Conservative directional shadow certificates from public observations only.

A negative observation n is known to be on the source's back side only when
the entire current source region lies strictly within its minimum 1000 m
reception radius. For positive observations a1, a2, a strict cone interior
point q = n + l1*(n-a1) + l2*(n-a2), l1,l2 > 0, is also on that back side:
h(q) = (1+l1+l2)*h(n)-l1*h(a1)-l2*h(a2) < 0.

The caller supplies previously observed positions. A distance check alone
never supplies either the negative direction fact or a positive observation.
"""
from itertools import combinations
import math
import numpy as np


def shadow_certificate(poly, positive_points, negative_points, q):
    """Return a two-positive-point shadow witness, or None when uncertain.

    Collinear, near-collinear, cone-boundary and numerically ill-conditioned
    cases are deliberately left unproved. The certificate is JSON-serializable.
    """
    try:
        poly = np.asarray(poly, dtype=float)
        positive = np.asarray(positive_points, dtype=float).reshape(-1, 2)
        negative = np.asarray(negative_points, dtype=float).reshape(-1, 2)
        query = np.asarray(q, dtype=float)
    except (TypeError, ValueError):
        return None
    if (poly.ndim != 2 or poly.shape[1] != 2 or not len(poly)
            or query.shape != (2,) or len(positive) < 2 or not len(negative)
            or not all(np.isfinite(array).all() for array in (poly, positive, negative, query))):
        return None
    for n in negative:
        # Convexity of the disk makes the all-vertex check sufficient. Strict
        # margin avoids certifying a no_signal caused by an uncertain radius.
        if np.linalg.norm(poly-n, axis=1).max() >= 1000.-1e-5:
            continue
        target = query-n
        target_norm = float(np.linalg.norm(target))
        if target_norm < 1e-5:
            continue
        for a1, a2 in combinations(positive, 2):
            u, v = n-a1, n-a2
            unorm, vnorm = float(np.linalg.norm(u)), float(np.linalg.norm(v))
            if min(unorm, vnorm) < 1e-5:
                continue
            determinant = float(u[0]*v[1]-u[1]*v[0])
            if abs(determinant) <= 1e-7*unorm*vnorm:
                continue
            l1 = float((target[0]*v[1]-target[1]*v[0])/determinant)
            l2 = float((u[0]*target[1]-u[1]*target[0])/determinant)
            if not all(math.isfinite(value) and 1e-7 < value < 1e6 for value in (l1, l2)):
                continue
            # Also require an angular margin from each cone boundary. Merely
            # positive rounded coefficients can be unreliable near a ray.
            cross_u = abs(float(u[0]*target[1]-u[1]*target[0]))
            cross_v = abs(float(v[0]*target[1]-v[1]*target[0]))
            if min(cross_u/(unorm*target_norm), cross_v/(vnorm*target_norm)) <= 1e-7:
                continue
            residual = np.linalg.norm(target-l1*u-l2*v)
            if residual > 1e-8*max(1., target_norm):
                continue
            return dict(negative_point=n.tolist(), positive_points=[a1.tolist(), a2.tolist()],
                        coefficients=[l1, l2])
    return None
