"""Once-only radial alignment AFTER selecting the first outer scan task."""
import math
from .geometry import stations


def align_first_entry(cover,station_id,position):
    if not 1<=station_id<=6:raise ValueError('Need an outer station')
    if math.hypot(*position)<=1e-9:return cover,0.
    phase=math.atan2(position[1],position[0])-(station_id-1)*math.pi/3
    radius=math.hypot(*cover[1])
    return stations(radius,phase),phase
