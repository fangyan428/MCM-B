"""Evaluator-only fresh layouts, crossed explicitly by family and source count."""
import math
import random

FAMILIES = ('uniform', 'outer', 'cluster', 'min_radius', 'radial', 'reception_edge')
MODES = ('spatial_hash', 'smooth', 'positive', 'negative')


def generate(start, repeats, prefix):
    cases = []
    index = 0
    for repeat in range(repeats):
        for family in FAMILIES:
            for count in range(10, 17):
                seed = start + index
                rng = random.Random(seed)
                channels = rng.sample(range(1, 21), count)
                phase = rng.uniform(0, 2 * math.pi)
                cluster_r = rng.uniform(100, 1700)
                cx, cy = cluster_r * math.cos(phase), cluster_r * math.sin(phase)
                sources = []
                for j, channel in enumerate(channels):
                    r = 1800 * math.sqrt(rng.random())
                    angle = rng.uniform(0, 2 * math.pi)
                    radius = rng.uniform(1000, 1500)
                    if family == 'outer':
                        r = rng.uniform(1600, 1800)
                        if (count + repeat) % 2:
                            angle = phase + rng.uniform(-.06, .06)
                    elif family == 'cluster':
                        x, y = cx + rng.uniform(-60, 60), cy + rng.uniform(-60, 60)
                        r, angle = math.hypot(x, y), math.atan2(y, x)
                    elif family == 'min_radius':
                        radius = 1000.
                    elif family == 'radial':
                        angle, r = phase + rng.uniform(-.002, .002), rng.uniform(0, 1800)
                        radius = 1000. if j % 2 else 1500.
                    elif family == 'reception_edge':
                        radius = 1000. if j % 2 else 1500.
                        r = radius + (-1 if j % 3 else 1) * rng.uniform(.001, 1.) if j % 4 else 1800.
                    r = min(1800., r)
                    sources.append(dict(channel=channel, x=r * math.cos(angle), y=r * math.sin(angle), radius=radius))
                for mode in MODES:
                    cases.append(dict(id=f'{prefix}_{family}_{seed}_{mode}', seed=seed,
                                      error_mode=mode, family=family, sources=sources))
                index += 1
    return cases
