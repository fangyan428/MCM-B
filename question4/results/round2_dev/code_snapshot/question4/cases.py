"""Evaluator-owned fixtures. Never imported by strategy or geometry."""
import math
import random

def make_case(seed, family='uniform', mode='spatial_hash'):
    rng=random.Random(seed)
    n=rng.randint(10,16); channels=rng.sample(range(1,21),n)
    sources=[]
    for i,ch in enumerate(channels):
        a=rng.uniform(0,2*math.pi)
        if family in ('outward','inward','tangent','edge'):
            r=rng.uniform(1660,1800)
        elif family=='cluster':
            a=rng.choice([.3,2.5,4.7])+rng.uniform(-.12,.12);r=rng.uniform(900,1400)
        else:
            r=1800*math.sqrt(rng.random())
        axis=rng.uniform(0,360)
        if family=='outward':axis=math.degrees(a)
        if family=='inward':axis=math.degrees(a)+180
        if family=='tangent':axis=math.degrees(a)+rng.choice([-90,90])
        # All benchmark fixtures contain both types, including extremes 1 and n-1 directional.
        directional=(i < (n-1 if seed%3==0 else 1 if seed%3==1 else n//2))
        sources.append(dict(channel=ch,x=r*math.cos(a),y=r*math.sin(a),
                            radius=1000 if family in ('outward','tangent') else rng.uniform(1000,1500),
                            direction_deg=axis%360 if directional else None))
    return dict(id=f'{family}_{seed}_{mode}',seed=seed,error_mode=mode,sources=sources,family=family)

def fixtures(seed,count):
    families=['uniform','outward','inward','tangent','cluster','edge']
    return [make_case(seed+i,families[i%len(families)]) for i in range(count)]
