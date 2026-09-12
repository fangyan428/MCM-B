"""New public-feedback mechanisms; independent from evaluator-owned fixtures."""
import math
from itertools import combinations
import numpy as np
from scipy.spatial import ConvexHull
from question4.strategy import Strategy as Baseline
from question4.geometry import estimate, clip, optical_cover

BASE = dict(scheduling='route', mesh_kind='radial', scan_known='certified',
            centroid_route=True, known_count_stop=True, scan_information=True)
CANDIDATES = {
    'CELL_OPTICAL': {'local_mechanism': 'cell_optical'},
    'CLEAR_DISCOVERY': {'local_mechanism': 'clear_discovery'},
    'NEGATIVE_REGION': {'local_mechanism': 'negative_region'},
}


def cell_cover(poly, angle, start):
    """Partition the bounding rectangle into strips and variable-width cells.

    Every retained polygon cell lies inside a rectangle of diagonal <40 m.
    All nonempty clipped cells are retained. Disks around their rectangle
    centers therefore cover the entire feasible region, including boundaries.
    """
    theta = math.radians(angle)
    axes = np.array([[math.cos(theta), -math.sin(theta)],
                     [math.sin(theta), math.cos(theta)]])
    p = poly @ axes
    low, high = p.min(0)-1e-7, p.max(0)+1e-7
    width, height = high-low
    options = []
    for ny in range(max(1, math.ceil(height/39)), max(2, math.ceil(height/20))+1):
        dy = height/ny
        if dy >= 39.999:
            continue
        dx_limit = math.sqrt(39.999**2-dy**2)
        nx = max(1, math.ceil(width/dx_limit))
        options.append((nx*ny, ny, nx))
    _, ny, nx = min(options)
    dx, dy = (high-low)/np.array([nx, ny])
    cells = []
    for j in range(ny):
        for i in (range(nx) if j%2==0 else reversed(range(nx))):
            lo=low+np.array([i*dx,j*dy]); hi=lo+[dx,dy]
            cell=p.copy()
            for normal, bound in (([1,0],hi[0]),([-1,0],-lo[0]),([0,1],hi[1]),([0,-1],-lo[1])):
                cell=clip(cell,normal,bound)
            if len(cell):
                cells.append(dict(vertices=(cell@axes.T).tolist(),
                                  center=(((lo+hi)/2)@axes.T).tolist(), index=[i,j]))
    if math.dist(start,cells[-1]['center']) < math.dist(start,cells[0]['center']):
        cells.reverse()
    return dict(vertices=poly.tolist(), angle=angle, low=low.tolist(), high=high.tolist(),
                shape=[nx,ny], cells=cells, radius=float(math.hypot(dx,dy)/2))


def prune_directional(poly, positive, negative):
    """Exclude strictly impossible source positions; convexify conservatively.

    If n is directionally negative and a,b positive, source s cannot equal
    n+l1*(n-a)+l2*(n-b), l1,l2>0. The affine emission function would give h(s)<0.
    Each complement halfplane is retained with a positive numerical margin.
    """
    proofs=[]
    for n0 in negative[-8:]:
        n=np.asarray(n0)
        if np.linalg.norm(poly-n,axis=1).max()>=1000-1e-5:
            continue
        for a0,b0 in combinations(positive[-8:],2):
            a,b=np.asarray(a0),np.asarray(b0)
            matrix=np.column_stack([n-a,n-b])
            if abs(np.linalg.det(matrix))<1e-5*np.linalg.norm(n-a)*np.linalg.norm(n-b):
                continue
            inv=np.linalg.inv(matrix)
            pieces=[clip(poly,normal,float(normal@n)+1e-6) for normal in inv]
            keep=[x for x in pieces if len(x)]
            if not keep:
                raise RuntimeError('Directional inference inconsistent with public observations')
            vertices=np.vstack(keep)
            if len(vertices)<3:
                continue
            try:
                new=vertices[ConvexHull(vertices).vertices]
            except Exception:
                continue
            old_area=ConvexHull(poly).volume
            if ConvexHull(new).volume < old_area-1e-5:
                proofs.append(dict(before=poly.tolist(),vertices=new.tolist(),negative_point=n.tolist(),
                                   positive_points=[a.tolist(),b.tolist()]))
                poly=new
    return poly,proofs


class Strategy(Baseline):
    def __init__(self,client,config,log=lambda row:None):
        self.mode=config['local_mechanism']
        if self.mode not in ('cell_optical','clear_discovery','negative_region'):
            raise ValueError('Unknown local mechanism')
        super().__init__(client,BASE,log)
        self.in_discovery=False

    def observe(self,p,ch,phase):
        kind=super().observe(p,ch,phase)
        if ch in self.known:
            self.log(dict(event='feasible_region',channel=int(ch),kind=kind,
                          vertices=self.known[ch]['poly'].tolist(),point=list(p)))
            if self.mode=='negative_region':
                poly,proofs=prune_directional(self.known[ch]['poly'],
                    [q for q,_ in self.readings[ch]],self.missed.get(ch,[]))
                self.known[ch]['poly']=poly
                for proof in proofs:
                    self.log(dict(event='directional_region_prune',channel=int(ch),**proof))
                if proofs:
                    self.log(dict(event='feasible_region',channel=int(ch),kind='directional_inference',
                                  vertices=poly.tolist(),point=list(p)))
        return kind

    def clear(self,p,ch,phase):
        before=tuple(self.c.position)
        ok=super().clear(p,ch,phase)
        if (ok and self.mode=='clear_discovery' and not self.in_discovery
                and math.dist(before,self.c.position)>1e-6 and len(self.known)+len(self.cleared)<16):
            self.in_discovery=True
            try:
                for other in range(1,21):
                    if other in self.known or other in self.cleared:
                        continue
                    self.observe(np.asarray(self.c.position),other,'clear_discovery')
                    if len(self.known)+len(self.cleared)==16:
                        break
            finally:
                self.in_discovery=False
        return ok

    def localize(self,ch):
        if self.mode!='cell_optical':
            return super().localize(ch)
        data=self.known[ch];center,radius=estimate(data['poly'])
        if radius>=20-1e-5 and len(self.readings[ch])<2:
            a=math.radians(data['angle']);side=np.array([-math.sin(a),math.cos(a)])
            probes=sorted([center+300*side,center-300*side],key=lambda q:math.dist(self.c.position,q))
            for q in probes:
                self.observe(q,ch,'localize')
                if ch in self.cleared:return
                if len(self.readings[ch])>=2:break
        data=self.known[ch];center,radius=estimate(data['poly'])
        if radius<20-1e-5:
            if not self.clear(center,ch,'certified_clear'):
                raise RuntimeError('Certified clear failed')
            return
        proof=cell_cover(data['poly'],data['angle'],self.c.position)
        self.log(dict(event='optical_cells',channel=int(ch),**proof))
        for cell in proof['cells']:
            if self.clear(cell['center'],ch,'optical_fallback'):return
        raise RuntimeError('Exhausted cell cover without successful clear')


def run(client,config,log=lambda row:None):
    return Strategy(client,config,log).run()
