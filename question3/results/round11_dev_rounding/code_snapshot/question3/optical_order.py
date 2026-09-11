"""Choose the nearer end of a fixed optical path, preserving its covering set."""
import math


def nearer_end(points,current):
    if math.dist(current,points[-1])+1e-8<math.dist(current,points[0]):
        return list(reversed(points))
    return points
