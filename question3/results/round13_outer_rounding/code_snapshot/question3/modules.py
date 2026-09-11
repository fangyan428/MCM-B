"""Optional public-information modules A (local cost), B (route via strategy), C (evidence).
No simulator/case imports. All design constants fixed before round-one comparison.
"""
import math
from functools import lru_cache
import numpy as np
from question2.strategy import candidate, diameters, to_world
from question1.solve import bearing_halfplanes
from .geometry import second_point
from .current_point import local_offset,current_proxy

OFFSETS=((400,500),(500,400),(500,500),(600,400),(700,450),(750,400),(800,605),(850,450))

@lru_cache(maxsize=8)
def design_catalog(error_deg=1.005, min_angle=20.):
    delta=math.radians(error_deg)
    r,alpha,error=np.meshgrid(np.linspace(5.001,1500,31),np.linspace(-delta,delta,3),
                              np.linspace(-delta,delta,3),indexing='ij')
    g=np.column_stack([(r*np.cos(alpha)).ravel(),(r*np.sin(alpha)).ravel()]);error=error.ravel()
    catalog=[]
    for a,b in OFFSETS:
        if not candidate([a,b],min_angle,error_deg):continue
        d=float(diameters([a,b],g,error,error_deg).max())
        h=a*math.cos(delta)-b*math.sin(delta)
        max_range=math.sqrt(max(a*a+b*b+25-10*h,a*a+b*b+1500**2-3000*h))
        # Surrogate only: diagonal-based box count can overcount or undercount.
        # Never used as a coverage/feasibility certificate or a probabilistic expectation.
        cells=math.ceil(d/28)*math.ceil(2*1500*math.sin(delta)/28)
        continuation=max_range/5+(3+28/5)*cells
        for sign in [1,-1]:
            catalog.append(dict(offset=(a,sign*b),sampled_worst_diameter=d,
                                max_source_distance=max_range,proxy_cells=cells,continuation_proxy_s=continuation))
    return tuple(catalog)


def choose_second(first,bearing,current,config):
    if not config.get('modules',{}).get('A',False):
        q=second_point(first,bearing,config['second_offset'],config['error_deg'],config['min_angle_deg'])
        return q,dict(mode='fixed',offset=config['second_offset'])
    best=None
    for row in design_catalog(config['error_deg'],config['min_angle_deg']):
        q=tuple(to_world(row['offset'],first,bearing))
        score=math.dist(current,q)/5+5+row['continuation_proxy_s']
        key=(score,row['offset'])
        if best is None or key<best[0]:best=(key,q,row)
    if best is None:raise RuntimeError('No certified second-point candidates')
    opportunity=config.get('second_point_opportunity','off')
    if opportunity!='off':
        offset=local_offset(first,bearing,current)
        row=current_proxy(offset,config['error_deg'],config['min_angle_deg'])
        if row is not None:
            score=5+row['continuation_proxy_s']
            if opportunity=='current_if_certified' or score<best[0][0]-1e-8:
                return tuple(current),dict(mode='opportunistic_current',score_s=score,**row,
                    min_angle_deg=config['min_angle_deg'],error_deg=config['error_deg'],
                    selection_rule=opportunity,catalog_score_s=best[0][0],catalog_point=best[1],
                    catalog_entry_distance_m=math.dist(current,best[1]),
                    catalog_sampled_diameter=best[2]['sampled_worst_diameter'])
    return best[1],dict(mode='cost_proxy',score_s=best[0][0],**best[2])


class EvidenceCover:
    """Finite covering debt. Fine cells are excluded only by whole-cell proofs.

    Every fine cell has its original coarse-grid centre within 20m of all corners.
    Failures remove cells fully inside failed-clear disks; they never infer absence
    from a bare centre test. Point selection uses covered geometric area per cost,
    not a probability of source presence. No fine-grid point estimate of truth.
    """
    def __init__(self,points,certificate,first,bearing,second,reading,negative_positions,error_deg,subdiv=4):
        v=np.asarray(certificate['vertices']);origin=np.asarray(first)
        angle=math.radians(bearing);rot=np.array([[math.cos(angle),-math.sin(angle)],[math.sin(angle),math.cos(angle)]])
        local=(v-origin)@rot;lo=local.min(axis=0)-1e-5;hi=local.max(axis=0)+1e-5
        sizes=np.maximum(1,np.ceil((hi-lo)/28).astype(int));fine=sizes*subdiv
        corners=[]
        for j in range(fine[1]):
            for i in range(fine[0]):
                cell=lo+(np.array([[i,j],[i+1,j],[i+1,j+1],[i,j+1]])/fine)*(hi-lo)
                corners.append(origin+cell@rot.T)
        self.corners=np.array(corners);self.points=np.asarray(points);self.alive=np.ones(len(corners),bool)
        self.untried=np.ones(len(points),bool);self.initial_count=len(corners);self.prior_dropped=0;self.failed_dropped=0
        A,b=bearing_halfplanes([dict(x=first[0],y=first[1],bearing_deg=bearing),
                              dict(x=second[0],y=second[1],bearing_deg=reading)],error_deg)
        projections=np.einsum('kd,nvd->nkv',A,self.corners)
        self.alive &= ~np.any(projections.min(axis=2)>b[None,:]+1e-7,axis=1)
        centres=self.corners.mean(axis=1);radii=np.linalg.norm(self.corners-centres[:,None,:],axis=2).max(axis=1)
        for centre,radius in [((0,0),1800),(first,1500),(second,1500)]:
            self.alive &= np.linalg.norm(centres-centre,axis=1)-radii <= radius+1e-7
        for p in negative_positions:
            self.alive &= np.linalg.norm(self.corners-np.asarray(p),axis=2).max(axis=1)>1000-1e-7
        self.prior_dropped=int(self.initial_count-self.alive.sum())
        self.covers=np.linalg.norm(self.points[:,None,None,:]-self.corners[None,:,:,:],axis=3).max(axis=2)<=20-1e-7
        if not np.all(self.covers.any(axis=0)):raise RuntimeError('Fine cells lack original optical coverage')
        if not self.alive.any():raise RuntimeError('All source cells excluded by prior evidence')
    def next_point(self,current):
        if not self.alive.any():raise RuntimeError('All feasible cells removed without success')
        gain=self.covers[:,self.alive].sum(axis=1)
        cost=3+np.linalg.norm(self.points-np.asarray(current),axis=1)/5
        scores=np.where(self.untried & (gain>0),gain/cost,-1)
        k=int(np.argmax(scores))
        if scores[k]<0:raise RuntimeError('Optical covering debt cannot be satisfied')
        self.untried[k]=False
        return k,tuple(self.points[k]),dict(remaining_cells=int(self.alive.sum()),fully_covered_cells=int(gain[k]))
    def failed(self,k):
        remove=self.alive & self.covers[k];self.failed_dropped+=int(remove.sum());self.alive[remove]=False
    def metrics(self):return dict(fine_cells=self.initial_count,prior_excluded_cells=self.prior_dropped,
                                  failed_clear_excluded_cells=self.failed_dropped,remaining_cells=int(self.alive.sum()))
