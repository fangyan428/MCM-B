"""Evaluator-only structured generators; policy never imports this module."""
import json
import math
import random
from pathlib import Path

FAMILIES=('uniform','outer','cluster','min_radius','radial','reception_edge')
MODES=('spatial_hash','smooth','positive','negative')

def generate(start,count,prefix):
    cases=[]
    for i,seed in enumerate(range(start,start+count)):
        rng=random.Random(seed);family=FAMILIES[i%6]
        n=rng.randint(10,16);channels=rng.sample(range(1,21),n)
        phase=rng.uniform(0,2*math.pi)
        cluster_r=rng.uniform(100,1700)
        cluster=(cluster_r*math.cos(phase),cluster_r*math.sin(phase))
        sources=[]
        for j,c in enumerate(channels):
            r=1800*math.sqrt(rng.random());a=rng.uniform(0,2*math.pi)
            receiver=rng.uniform(1000,1500)
            if family=='outer':
                r=rng.uniform(1600,1800)
                if i%12==1:a=phase+rng.uniform(-.06,.06)
            elif family=='cluster':
                x=cluster[0]+rng.uniform(-60,60);y=cluster[1]+rng.uniform(-60,60)
                r=math.hypot(x,y);a=math.atan2(y,x)
            elif family=='min_radius':receiver=1000.
            elif family=='radial':
                a=phase+rng.uniform(-.002,.002);r=rng.uniform(0,1800)
                receiver=1000. if j%2 else 1500.
            elif family=='reception_edge':
                receiver=1000. if j%2 else 1500.
                # Around origin reception threshold; remaining sources on domain boundary.
                r=receiver+(-1 if j%3 else 1)*rng.uniform(.001,1.) if j%4 else 1800.
            r=min(1800,r)
            sources.append(dict(channel=c,x=r*math.cos(a),y=r*math.sin(a),radius=receiver))
        for mode in MODES:
            cases.append(dict(id=f'{prefix}_{family}_{seed}_{mode}',seed=seed,error_mode=mode,family=family,sources=sources))
    return cases

if __name__=='__main__':
    root=Path(__file__).resolve().parent
    out=root/'structured_development.json'
    if out.exists():raise SystemExit('Refusing to overwrite fixtures')
    out.write_text(json.dumps(generate(900000,60,'structdev'),indent=2))
