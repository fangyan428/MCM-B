"""S: certify another already-detected source at a shared second point."""
import math
from question2.strategy import candidate


def compatible_offset(first,bearing,point,error_deg,min_angle):
    a=math.radians(bearing);dx=point[0]-first[0];dy=point[1]-first[1]
    q=(dx*math.cos(a)+dy*math.sin(a),-dx*math.sin(a)+dy*math.cos(a))
    return q if candidate(q,min_angle,error_deg) else None


def choose_shared(primary,point,first,cleared,cached,config):
    for channel in sorted(first):
        if channel==primary or channel in cleared or channel in cached:continue
        offset=compatible_offset(*first[channel],point,config['error_deg'],config['min_angle_deg'])
        if offset is not None:
            return channel,dict(mode='shared_certified',offset=offset,shared_with=primary,
                                error_deg=config['error_deg'],min_angle_deg=config['min_angle_deg'])
    return None
