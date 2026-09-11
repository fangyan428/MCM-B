"""S: certify another already-detected source at a shared second point."""
import math
from question2.strategy import candidate


def compatible_offset(first,bearing,point,error_deg,min_angle):
    a=math.radians(bearing);dx=point[0]-first[0];dy=point[1]-first[1]
    q=(dx*math.cos(a)+dy*math.sin(a),-dx*math.sin(a)+dy*math.cos(a))
    return q if candidate(q,min_angle,error_deg) else None


def choose_shared(primary,point,first,cleared,cached,config,primary_points=None,decision_log=lambda e:None):
    mode=config.get('shared_selection','lowest_id')
    if mode not in ('lowest_id','cost_gate'):raise ValueError('Invalid shared selection mode')
    ranked=[]
    for channel in sorted(first):
        if channel==primary or channel in cleared or channel in cached:continue
        offset=compatible_offset(*first[channel],point,config['error_deg'],config['min_angle_deg'])
        if offset is not None:
            selection=dict(mode='shared_certified',offset=offset,shared_with=primary,
                           error_deg=config['error_deg'],min_angle_deg=config['min_angle_deg'])
            if mode=='lowest_id':return channel,selection
            if not primary_points:raise ValueError('Cost gate needs the primary optical plan')
            from .shared_cost import shared_saving
            prediction=shared_saving(*first[channel],offset,primary_points,config)
            ranked.append((channel,{**selection,**prediction, 'gate_mode':mode}))
    if mode=='cost_gate':
        acceptable=[row for row in ranked if row[1]['predicted_saving_s']>1e-8]
        selected=min(acceptable,key=lambda row:(-row[1]['predicted_saving_s'],row[0])) if acceptable else None
        decision_log(dict(type='shared_gate',primary_channel=primary,selected_channel=selected[0] if selected else None,
                          candidates=[dict(channel=c,**s) for c,s in ranked]))
        return selected
    return None
