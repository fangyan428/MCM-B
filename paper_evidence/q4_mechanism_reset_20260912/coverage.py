"""Experimental Q4 coverage policies. Strategies use public feedback only.

No fixtures, simulator state, true source count, direction or radius are inputs.
The continuous cell certificate is deterministic and based on public geometry.
"""
import math
from functools import lru_cache
import numpy as np
from scipy.spatial import ConvexHull, Delaunay, QhullError
from scipy.optimize import minimize
from question4.strategy import Strategy as Baseline
from question4.geometry import estimate
from question4.routing import tour

BASELINE_CONFIG = dict(scheduling='route', mesh_kind='radial', scan_known='certified',
                       centroid_route=True, known_count_stop=True, scan_information=True)
CANDIDATES = {
    'COVER_EXCHANGE': {'mechanism': 'exchange', 'certificate': 'cells'},
    'COVER_EXCHANGE_TRI': {'mechanism': 'exchange', 'certificate': 'triangles'},
    'COVER_ELASTIC': {'mechanism': 'elastic'},
    'COVER_SEARCH_FIRST': {'mechanism': 'search_first'},
    'COVER_SECTOR': {'mechanism': 'sector'},
    'COVER_EXCHANGE_ELASTIC': {'mechanism': 'exchange_elastic', 'certificate': 'cells'},
}


def triangle_certificate(points):
    """Sufficient continuous cover: Delaunay mesh + enclosing convex hull."""
    p = np.asarray(points, float)
    try:
        hull = ConvexHull(p)
        if np.max(hull.equations[:, 2] + 1800) > -1e-6:
            return None
        triangles = Delaunay(p).simplices
    except QhullError:
        return None
    v = p[triangles]
    if np.linalg.norm(v[:, :, None, :] - v[:, None, :, :], axis=3).max() >= 1000-1e-6:
        return None
    return triangles


@lru_cache(maxsize=16384)
def _cell(box):
    x0, y0, x1, y1 = box
    corners = np.array([(x0,y0),(x1,y0),(x1,y1),(x0,y1)])
    dx, dy = max(x0,0,-x1), max(y0,0,-y1)
    return corners, dx*dx+dy*dy > 1800**2


def cell_certificate(points, depth_limit=10):
    """Finite sufficient cover; returns None if proof budget is exhausted.

    Every retained box is inside the convex hull of stations that are within
    1000 m of all its corners. Convexity proves the property throughout the box.
    Rejection says only this proof attempt failed, not that the cover is false.
    """
    p = np.asarray(points, float)
    # The convex hull is a necessary condition and a cheap early rejection.
    try:
        if np.max(ConvexHull(p).equations[:,2]+1800) > -1e-6:
            return None
    except QhullError:
        return None
    leaves=[]; stack=[('',(-1800.,-1800.,1800.,1800.))]
    while stack:
        key, box=stack.pop(); corners, outside=_cell(box)
        if outside:
            leaves.append({'key':key,'outside':True});continue
        ids=np.flatnonzero(np.linalg.norm(p[:,None]-corners[None,:],axis=2).max(axis=1)<1000-1e-6)
        if len(ids)>=3:
            try:
                hull=ConvexHull(p[ids]); h=hull.equations
                if np.max(corners@h[:,:2].T+h[:,2])<=1e-8:
                    leaves.append({'key':key,'witnesses':ids[hull.vertices].tolist()});continue
            except QhullError:
                pass
        if len(key)==depth_limit:
            return None
        x0,y0,x1,y1=box;xm=(x0+x1)/2;ym=(y0+y1)/2
        children=((x0,y0,xm,ym),(xm,y0,x1,ym),(x0,ym,xm,y1),(xm,ym,x1,y1))
        stack.extend((key+str(i), child) for i,child in enumerate(children))
    return {'stations':p.tolist(),'leaves':leaves,'failed_cells':[]}


class Strategy(Baseline):
    def __init__(self, client, config, log=lambda row:None):
        allowed={'mechanism','certificate','baseline_config'}
        if set(config)-allowed:
            raise ValueError('Unknown coverage config: '+str(set(config)-allowed))
        self.options={'mechanism':'exchange','certificate':'cells'}|config
        if self.options['mechanism'] not in {'exchange','elastic','search_first','sector','exchange_elastic'}:
            raise ValueError('Unknown coverage mechanism')
        if self.options['certificate'] not in {'cells','triangles'}:
            raise ValueError('Unknown certificate')
        super().__init__(client, config.get('baseline_config',BASELINE_CONFIG),log)
        if self.cfg['mesh_kind']!='radial':
            raise ValueError('Coverage experiment requires the frozen 25-station parent')
        self.stations=self.stations.copy();self.triangles=self.triangles.copy()
        self._in_exchange=False;self._elastic_prepared=set();self._cell_cover=None
        self._exchange_checks=set()

    def _scan(self,i,p):
        channels=[ch for ch in range(1,21) if ch not in self.cleared]
        if self.c.channel in channels:
            channels.remove(self.c.channel);channels.insert(0,self.c.channel)
        for ch in channels:
            if ch in self.known:
                radius=estimate(self.known[ch]['poly'])[1]
                if self.cfg['scan_known']=='none' or (self.cfg['scan_known']=='certified' and radius<20-1e-5):
                    continue
                if self.cfg['scan_information']:
                    poly=self.known[ch]['poly'];center,_=estimate(poly);delta=poly-p
                    ref=math.atan2(center[1]-p[1],center[0]-p[0])
                    angles=(np.arctan2(delta[:,1],delta[:,0])-ref+math.pi)%(2*math.pi)-math.pi
                    if np.ptp(angles)<math.radians(3):continue
            self.observe(p,ch,'search');self.seen.add((i,ch))
        self.done.add(i)

    def _exchange_here(self):
        if self._in_exchange or len(self.cleared)+len(self.known)==16:
            return
        p=np.asarray(self.c.position,float)
        remaining=sorted((i for i in range(len(self.stations)) if i not in self.done),
                         key=lambda i:(math.dist(p,self.stations[i]),i))
        # Spatial locality is a fixed proof-computation budget, not a claim of
        # invisible-source absence. The original pending station is the fallback.
        for i in remaining[:3]:
            if math.dist(p,self.stations[i])>300:continue
            key=(i,tuple(p),tuple(self.stations.ravel()))
            if key in self._exchange_checks:continue
            self._exchange_checks.add(key)
            proposal=self.stations.copy();proposal[i]=p
            triangles=triangle_certificate(proposal);cover=None
            if triangles is None and self.options['certificate']=='cells':
                cover=cell_certificate(proposal)
            if triangles is None and cover is None:continue
            old=self.stations[i].copy();self.stations[i]=p
            self.triangles=triangles if triangles is not None else np.empty((0,3),dtype=int)
            self._cell_cover=cover
            self.log({'event':'coverage_exchange','station':i,'old':old.tolist(),'point':p.tolist(),
                      'certificate':'cells' if cover is not None else 'triangles',
                      'avoided_station_offset_m':math.dist(old,p)})
            self._in_exchange=True
            try:self._scan(i,p)
            finally:self._in_exchange=False
            return

    def clear(self,p,ch,phase):
        ok=super().clear(p,ch,phase)
        if ok and phase!='near' and self.options['mechanism'] in {'exchange','exchange_elastic'}:
            self._exchange_here()
        return ok

    def _elastic(self,i):
        """Move an unvisited interior station within a certified mesh cell.

        The objective accounts for the incoming leg and one public nearest task.
        Feasibility preserves old oriented faces and all incident edge bounds;
        an independent Delaunay+outer hull check is still required before commit.
        """
        if i in self.done or i==0 or i>=13:return
        p=self.stations[i].copy();start=np.asarray(self.c.position)
        other=[self.stations[j] for j in range(len(self.stations)) if j not in self.done and j!=i]
        other += [self.target(data) for data in self.known.values()]
        if not other:return
        nxt=min(other,key=lambda q:math.dist(p,q))
        triangles=triangle_certificate(self.stations)
        if triangles is None:return
        incident=[t for t in triangles if i in t]
        neighbors=sorted({int(j) for t in incident for j in t if j!=i})
        def cost(q):return float(np.linalg.norm(q-start)+np.linalg.norm(q-nxt))
        def feasible(q):
            vals=[(1000-1e-4)**2-float(np.sum((q-self.stations[j])**2)) for j in neighbors]
            for tri in incident:
                old=self.stations[tri];v=old.copy();v[list(tri).index(i)]=q
                sign=np.sign(np.cross(old[1]-old[0],old[2]-old[0]))
                vals.append(float(sign*np.cross(v[1]-v[0],v[2]-v[0]))-1e-4)
            return np.array(vals)
        opt=minimize(cost,p,method='SLSQP',constraints={'type':'ineq','fun':feasible},
                     options={'maxiter':35,'ftol':1e-5})
        if not opt.success or cost(opt.x)>=cost(p)-1e-3:return
        proposal=self.stations.copy();proposal[i]=opt.x;cert=triangle_certificate(proposal)
        if cert is None:return
        self.stations[i]=opt.x;self.triangles=cert;self._cell_cover=None
        self.log({'event':'coverage_elastic','station':i,'old':p.tolist(),'point':opt.x.tolist(),
                  'local_path_saving_m':cost(p)-cost(opt.x)})

    def observe(self,p,ch,phase):
        if phase=='search' and self.options['mechanism'] in {'elastic','exchange_elastic'} and not self._in_exchange:
            # Baseline p is a view of stations[i], hence the one committed move
            # also updates all channels in that same original scanning batch.
            ids=np.flatnonzero(np.linalg.norm(self.stations-p,axis=1)<1e-8)
            if len(ids)==1 and int(ids[0]) not in self._elastic_prepared:
                i=int(ids[0]);self._elastic_prepared.add(i);self._elastic(i)
        return super().observe(p,ch,phase)

    def _finish(self):
        certified=len(self.cleared)==16 or (len(self.done)==len(self.stations) and not self.known)
        if not certified:raise RuntimeError('Missing stop certificate')
        self.c.exit()
        return dict(status='complete',cleared=sorted(self.cleared),metrics=self.c.metrics(),
                    stop_certificate=dict(kind='count16' if len(self.cleared)==16 else 'triangular_halfplane_cover',
                    cover_sha256=None,spacing=self.cfg['spacing'],mesh_kind='radial',
                    stations=self.stations.tolist(),triangles=self.triangles.tolist(),
                    completed_stations=sorted(self.done),scanned_pairs=len(self.seen)))

    def _survey_run(self,sector=False):
        self.c.enter();active_sector=0
        # Four fixed 90-degree sectors define committed contiguous work areas.
        # This is scheduling only; all 25 original witness stations remain.
        def region(p):return int(((math.atan2(p[1],p[0])+2*math.pi)%(2*math.pi))/(math.pi/2))
        while len(self.done)<len(self.stations) or self.known:
            if len(self.cleared)==16:break
            remaining=[i for i in range(len(self.stations)) if i not in self.done]
            if len(self.cleared)+len(self.known)==16:remaining=[]
            if sector and remaining:
                local=[i for i in remaining if region(self.stations[i])==active_sector]
                known=[ch for ch,data in self.known.items() if region(self.target(data))==active_sector]
                if not local and not known:
                    active_sector=(active_sector+1)%4;continue
            else:local=remaining;known=list(self.known)
            # Search-first delays every source until the witness sweep ends.
            tasks=[('station',i,self.stations[i]) for i in local]
            if sector or not remaining:
                tasks += [('source',ch,self.target(self.known[ch])) for ch in known]
            if not tasks:
                # Sources whose estimate crossed a completed sector are handled
                # once all stations finish; no source is dropped from the queue.
                if self.known:tasks=[('source',ch,self.target(data)) for ch,data in self.known.items()]
                else:break
            order=tour(self.c.position,[t[2] for t in tasks]);kind,key,p=tasks[order[0]]
            if kind=='source':self.localize(key)
            else:self._scan(key,p)
        return self._finish()

    def run(self):
        mechanism=self.options['mechanism']
        result=self._survey_run(mechanism=='sector') if mechanism in {'search_first','sector'} else super().run()
        if result['stop_certificate']['kind']!='count16' and self._cell_cover is not None:
            result['stop_certificate']['kind']='dynamic_cell_halfplane_cover'
            result['stop_certificate']['dynamic_cover']=self._cell_cover
        return result


def run(client,config=None,log=lambda row:None):
    return Strategy(client,config or {},log).run()
