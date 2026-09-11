"""Question 1: bearing-wedge intersection; units metres/degrees.
Run: python question1/solve.py [measurements.json]
JSON input: [{"x": 0, "y": 0, "bearing_deg": 45}, ...]
Requires numpy, scipy. No simulator calls.
"""
import json
import sys
from itertools import combinations
from pathlib import Path
import numpy as np
from scipy.optimize import linprog


def bearing_halfplanes(measurements, error_deg=1.0):
    if not 0 < error_deg < 90:
        raise ValueError('error_deg must lie in (0, 90)')
    A, b = [], []
    for item in measurements:
        x, y, theta = (float(item[k]) for k in ('x', 'y', 'bearing_deg'))
        if not np.isfinite([x, y, theta]).all():
            raise ValueError('Non-finite measurement')
        lo, hi = np.deg2rad([(theta % 360)-error_deg, (theta % 360)+error_deg])
        # cross(u_lo, p-s)>=0; cross(u_hi, p-s)<=0.
        for normal in ([np.sin(lo), -np.cos(lo)], [-np.sin(hi), np.cos(hi)]):
            A.append(normal)
            b.append(np.dot(normal, [x, y]))
    if not A:
        raise ValueError('At least one bearing is required')
    return np.array(A), np.array(b)


def solve_halfplanes(A, b, tol=1e-7):
    A, b = np.asarray(A, float), np.asarray(b, float)
    if A.ndim != 2 or A.shape[1] != 2 or b.shape != (len(A),) or not len(A):
        raise ValueError('Expected nonempty A[m,2], b[m]')
    if not np.isfinite(A).all() or not np.isfinite(b).all():
        raise ValueError('Non-finite half-plane')
    lengths = np.linalg.norm(A, axis=1)
    if np.any(lengths == 0):
        raise ValueError('Zero half-plane normal')
    A, b = A / lengths[:, None], b / lengths
    def lp(c):
        return linprog(c, A_ub=A, b_ub=b, bounds=[(None, None)]*2,
                       method='highs', options={'primal_feasibility_tolerance': 1e-9})
    feasible = lp([0, 0])
    if feasible.status == 2:
        return {'status': 'empty', 'diameter': None, 'vertices': []}
    if not feasible.success:
        raise RuntimeError(feasible.message)
    for c in ([1, 0], [-1, 0], [0, 1], [0, -1]):
        result = lp(c)
        if result.status == 3:
            return {'status': 'unbounded', 'diameter': None, 'vertices': []}
        if not result.success:
            raise RuntimeError(result.message)
    vertices = []
    for i, j in combinations(range(len(A)), 2):
        M = A[[i, j]]
        if abs(np.linalg.det(M)) <= 1e-12:
            continue
        p = np.linalg.solve(M, b[[i, j]])
        if np.all(A @ p <= b + tol) and not any(np.linalg.norm(p-q) <= tol for q in vertices):
            vertices.append(p)
    if not vertices:
        raise RuntimeError('No vertices recovered: numerical degeneracy; use higher precision')
    v = np.array(vertices)
    order = np.argsort(np.arctan2(v[:, 1]-v[:, 1].mean(), v[:, 0]-v[:, 0].mean()))
    v = v[order]
    d2 = np.sum((v[:, None, :]-v[None, :, :])**2, axis=2)
    i, j = np.unravel_index(np.argmax(d2), d2.shape)
    D = float(np.sqrt(d2[i, j]))
    center = (v[i]+v[j])/2
    distances = np.linalg.norm(v-center, axis=1)
    return {'status': 'bounded', 'vertices': v.tolist(), 'diameter': D,
            'diameter_endpoints': [v[i].tolist(), v[j].tolist()],
            'diameter_circle_center': center.tolist(),
            'diameter_circle_covers': bool(np.max(distances) <= D/2+tol),
            'max_distance_to_diameter_center': float(np.max(distances))}


def solve(measurements, error_deg=1.0):
    return solve_halfplanes(*bearing_halfplanes(measurements, error_deg))


def triangle_measurements():
    vertices = np.array([[0., 0.], [20., 0.], [10., 10*np.sqrt(3)]])
    data = []
    for i in range(3):
        u = (vertices[(i+1) % 3]-vertices[i])/20
        s = vertices[i]-1000*u
        data.append({'x': float(s[0]), 'y': float(s[1]),
                     'bearing_deg': float((np.rad2deg(np.arctan2(u[1], u[0]))+1) % 360)})
    return data


if __name__ == '__main__':
    data = json.loads(Path(sys.argv[1]).read_text()) if len(sys.argv)>1 else triangle_measurements()
    print(json.dumps({'measurements': data, 'result': solve(data)}, ensure_ascii=False, indent=2))
