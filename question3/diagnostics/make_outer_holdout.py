"""Evaluator-only fresh outer-source stress fixtures after the same algorithm lock."""
import hashlib
import json
import math
from pathlib import Path
import random


def main():
    root=Path('question3/results');lock=json.loads((root/'round4_lock.json').read_text())
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in lock['code_sha256'].items())
    out=root/'round4_outer_holdout_cases.json';assert not out.exists();cases=[]
    for seed in range(30000,30020):
        rng=random.Random(seed);n=rng.randint(10,16);channels=rng.sample(range(1,21),n);centre=rng.uniform(0,2*math.pi);sources=[]
        for c in channels:
            radius=rng.uniform(1600,1800);angle=centre+rng.uniform(-.06,.06) if seed%2 else rng.uniform(0,2*math.pi)
            sources.append(dict(channel=c,x=radius*math.cos(angle),y=radius*math.sin(angle),radius=rng.uniform(1000,1500)))
        for mode in lock['error_modes']:
            cases.append(dict(id=f'outer_holdout_{seed}_{mode}',seed=seed,error_mode=mode,sources=sources))
    out.write_text(json.dumps(cases,indent=2));print(len(cases),hashlib.sha256(out.read_bytes()).hexdigest())

if __name__=='__main__':main()
