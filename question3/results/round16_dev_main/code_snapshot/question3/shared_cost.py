"""G: comparable complete-secondary-task costs for shared measurement selection.
A sampled planning proxy, NOT a continuous cost bound or a probability model.
"""
import math
from functools import lru_cache
import numpy as np
from question2.strategy import diameters
from .modules import choose_second


@lru_cache(maxsize=2048)
def shared_shape_proxy(offset,error_deg):
    delta=math.radians(error_deg)
    r,a,e=np.meshgrid(np.linspace(5.001,1500,31),np.linspace(-delta,delta,3),np.linspace(-delta,delta,3),indexing='ij')
    g=np.column_stack([(r*np.cos(a)).ravel(),(r*np.sin(a)).ravel()])
    d=float(diameters(offset,g,e.ravel(),error_deg).max())
    cells=math.ceil(d/28)*math.ceil(2*1500*math.sin(delta)/28)
    return cells,d,g.reshape(31,3,3,2)[:,:,0,:].reshape(-1,2)


def shared_saving(first,bearing,offset,primary_points,config):
    cells,d,local=shared_shape_proxy(tuple(offset),config['error_deg'])
    angle=math.radians(bearing);rot=np.array([[math.cos(angle),-math.sin(angle)],[math.sin(angle),math.cos(angle)]])
    targets=np.asarray(first)+local@rot.T
    best_lower=math.inf;travel_at_worst=grid_at_worst=None
    for endpoint in primary_points:
        independent,selection=choose_second(first,bearing,endpoint,config)
        if 'proxy_cells' not in selection:raise ValueError('Shared cost gate requires A metadata')
        travel=(math.dist(endpoint,independent)+np.linalg.norm(targets-independent,axis=1)-np.linalg.norm(targets-endpoint,axis=1))/5
        grid=8.6*(selection['proxy_cells']-cells)
        saving=float(travel.min())+grid
        if saving<best_lower:best_lower=saving;travel_at_worst=float(travel.min());grid_at_worst=float(grid)
    return dict(predicted_saving_s=best_lower,travel_proxy_s=travel_at_worst,grid_proxy_s=grid_at_worst,
                shared_proxy_cells=cells,shared_sampled_diameter_m=d,terminal_count=len(primary_points),source_samples=len(targets))
