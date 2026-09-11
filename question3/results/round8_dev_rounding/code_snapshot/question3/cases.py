"""Self-case fixtures; never imported by strategy. Fixed development seeds only."""
import math
import random

def random_case(seed,error_mode='spatial_hash'):
    rng=random.Random(seed);n=rng.randint(10,16);channels=rng.sample(range(1,21),n)
    sources=[]
    for c in channels:
        r=1800*math.sqrt(rng.random());a=rng.uniform(0,2*math.pi)
        sources.append(dict(channel=c,x=r*math.cos(a),y=r*math.sin(a),radius=rng.uniform(1000,1500)))
    return dict(id=f'dev_{seed}_{error_mode}',seed=seed,error_mode=error_mode,sources=sources)

def boundary_case():
    # 16 sources, minimum receiver radius, circle edge + station-sector bisectors.
    return dict(id='boundary_minR_16',seed=77,error_mode='positive',sources=[
        dict(channel=c,x=1800*math.cos((c-.5)*2*math.pi/16),y=1800*math.sin((c-.5)*2*math.pi/16),radius=1000.)
        for c in range(1,17)])

def late_source_case():
    # First ten are easy to find at origin; 11th, channel20, is found at the last ring station.
    sources=[dict(channel=c,x=20*c,y=0.,radius=1000.) for c in range(1,11)]
    a=5*math.pi/3
    sources.append(dict(channel=20,x=1800*math.cos(a),y=1800*math.sin(a),radius=1000.))
    return dict(id='late_channel20_after_ten',seed=9,error_mode='negative',sources=sources)

def near_case():
    case=random_case(888,'smooth');case['id']='near_at_origin';case['sources'][0].update(x=0.,y=0.,channel=case['sources'][0]['channel'])
    return case

def clustered_case():
    sources=[dict(channel=c,x=1500.+c*.1,y=-.1*c,radius=1500.) for c in range(1,17)]
    return dict(id='clustered_16',seed=12,error_mode='smooth',sources=sources)

def development_cases():
    yield from [random_case(seed,mode) for mode in ['spatial_hash','smooth','positive','negative'] for seed in range(12)]
    yield from [boundary_case(),late_source_case(),near_case(),clustered_case()]
