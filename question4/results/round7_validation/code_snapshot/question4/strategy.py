"""Certified directional search; accepts only a public action client and fixed config."""
import math
import numpy as np
from .geometry import mesh, radial_mesh, compact_mesh, cover_hash, first_region, bearing_clip, optical_cover, estimate, bbox
from .routing import tour

DEFAULT = dict(spacing=990., search_order='nearest', scheduling='immediate',
               localization='pair', probe_width=300., opportunistic_clear=False,
               shared_scan=False, optical_order='snake', refinement=False, joint_weight=1.,
               mesh_kind='lattice', scan_known='all')
DEFAULT.update(centroid_route=False, detection_cost_route=False, known_count_stop=False)
DEFAULT.update(centroid_probe=False,relocate_route=False,scan_information=False)

class Strategy:
    def __init__(self, client, config, log=lambda x:None):
        if set(config)-set(DEFAULT):raise ValueError('Unknown configuration fields: '+str(set(config)-set(DEFAULT)))
        self.c=client; self.cfg=DEFAULT|config; self.log=log
        for key,allowed in dict(scheduling={'immediate','joint','route'},localization={'pair','optical'},
                mesh_kind={'lattice','radial','compact'},scan_known={'all','none','certified'}).items():
            if self.cfg[key] not in allowed:raise ValueError('Invalid '+key)
        if not math.isfinite(self.cfg['probe_width']) or not 10<=self.cfg['probe_width']<=1000:
            raise ValueError('Invalid probe width')
        for key,value in DEFAULT.items():
            if isinstance(value,bool) and not isinstance(self.cfg[key],bool):raise ValueError('Invalid boolean '+key)
        self.stations,self.triangles=(compact_mesh() if self.cfg['mesh_kind']=='compact' else
            radial_mesh() if self.cfg['mesh_kind']=='radial' else mesh(self.cfg['spacing']))
        self.cleared=set(); self.known={}; self.seen=set()
        self.readings={}; self.missed={}; self.done=set()

    def observe(self,p,ch,phase):
        r=self.c.measure(p,int(ch),phase)
        kind=r['measure_result']
        if kind=='near':
            if not self.clear(p,ch,'near'):
                raise RuntimeError('Near clear failed')
        elif kind=='direction':
            a=r['svd_deg']
            if ch in self.known:
                self.known[ch]['poly']=bearing_clip(self.known[ch]['poly'],p,a)
            else:
                self.known[ch]=dict(poly=first_region(p,a),first=np.array(p),angle=a)
            self.readings.setdefault(ch,[]).append((list(p),a))
        else:
            self.missed.setdefault(ch,[]).append(list(p))
        self.log(dict(event='observe',channel=int(ch),point=list(p),kind=kind))
        return kind

    def clear(self,p,ch,phase):
        ok=self.c.clear(p,int(ch),phase)['clear_result']=='success'
        if ok:
            self.cleared.add(ch); self.known.pop(ch,None)
        return ok

    def target(self,data):
        poly=data['poly']
        if not self.cfg['centroid_route']:return estimate(poly)[0]
        q=np.roll(poly,-1,axis=0);cross=poly[:,0]*q[:,1]-q[:,0]*poly[:,1]
        if abs(cross.sum())<1e-8:return estimate(poly)[0]
        return ((poly+q)*cross[:,None]).sum(axis=0)/(3*cross.sum())

    def localize(self,ch):
        data=self.known[ch]; poly=data['poly']; center,radius=estimate(poly)
        if radius<20-1e-5:
            if not self.clear(center,ch,'certified_clear'):
                raise RuntimeError('Certified clear failed')
            return
        if self.cfg['localization']=='pair' and len(self.readings[ch])<2:
            a=math.radians(data['angle']); v=np.array([-math.sin(a),math.cos(a)])
            probe_center=self.target(data) if self.cfg['centroid_probe'] else center
            candidates=[probe_center+self.cfg['probe_width']*v,probe_center-self.cfg['probe_width']*v]
            candidates.sort(key=lambda q:math.dist(self.c.position,q))
            for q in candidates:
                self.observe(q,ch,'localize')
                if ch in self.cleared:
                    return
                if len(self.readings[ch])>=2:
                    break
        if ch not in self.known:
            return
        data=self.known[ch]; poly=data['poly']; center,radius=estimate(poly)
        if self.cfg['refinement'] and radius>35:
            # A third bearing is valuable only when the existing region is expensive to sweep.
            lo,hi,rot=bbox(poly,data['angle'])
            direction=rot[:,int(np.argmax(hi-lo))]
            normal=np.array([-direction[1],direction[0]])
            width=max(45.,min(180.,radius*.6))
            proposals=[center+width*normal,center-width*normal]
            proposals.sort(key=lambda q:math.dist(self.c.position,q))
            for q in proposals:
                kind=self.observe(q,ch,'refine')
                if ch in self.cleared:return
                if kind=='direction':break
            poly=self.known[ch]['poly'];center,radius=estimate(poly)
        if radius<20-1e-5:
            if not self.clear(center,ch,'certified_clear'):
                raise RuntimeError('Certified clear failed')
            return
        points,r=optical_cover(poly,data['angle'],self.c.position)
        if self.cfg['opportunistic_clear']:
            if self.clear(center,ch,'center_attempt'):return
        self.log(dict(event='optical_cover',channel=int(ch),vertices=poly.tolist(),cover_radius=r,points=len(points)))
        for q in points:
            if self.clear(q,ch,'optical_fallback'):
                return
        raise RuntimeError('Exhausted optical certificate without success')

    def run(self):
        self.c.enter()
        while len(self.done)<len(self.stations) or self.known:
            if len(self.cleared)==16:
                break
            remaining=[i for i in range(len(self.stations)) if i not in self.done]
            if self.cfg['known_count_stop'] and len(self.cleared)+len(self.known)==16:
                remaining=[]
            i=min(remaining,key=lambda j:(math.dist(self.c.position,self.stations[j]),j)) if remaining else None
            route_choice=None
            if self.cfg['scheduling']=='route':
                tasks=[('station',j,self.stations[j]) for j in remaining]+[('source',ch,self.target(data)) for ch,data in self.known.items()]
                weights=[6. if t[0]=='source' and (self.cfg['scan_known']!='certified' or estimate(self.known[t[1]]['poly'])[1]>=20-1e-5) else 0. for t in tasks]
                flags=[float(t[0]=='station') for t in tasks]
                order=tour(self.c.position,[t[2] for t in tasks],weights if self.cfg['detection_cost_route'] else None,flags,self.cfg['relocate_route'])
                route_choice=tasks[order[0]]
                if route_choice[0]=='source':
                    self.localize(route_choice[1]);continue
                i=route_choice[1]
            if self.known:
                ch=min(self.known,key=lambda c:math.dist(self.c.position,estimate(self.known[c]['poly'])[0]))
                source_cost=math.dist(self.c.position,estimate(self.known[ch]['poly'])[0])/5
                station_cost=math.inf if i is None else math.dist(self.c.position,self.stations[i])/5+(20-len(self.cleared))*6*self.cfg['joint_weight']
                if self.cfg['scheduling']=='immediate' or (route_choice is None and source_cost<=station_cost):
                    self.localize(ch)
                    continue
            if not remaining:
                break
            p=self.stations[i]
            channels=[ch for ch in range(1,21) if ch not in self.cleared]
            if self.c.channel in channels:
                channels.remove(self.c.channel);channels.insert(0,self.c.channel)
            for ch in channels:
                if ch in self.known:
                    radius=estimate(self.known[ch]['poly'])[1]
                    if self.cfg['scan_known']=='none' or (self.cfg['scan_known']=='certified' and radius<20-1e-5):
                        continue
                    if self.cfg['scan_information']:
                        poly=self.known[ch]['poly'];center,_=estimate(poly)
                        delta=poly-p
                        ref=math.atan2(center[1]-p[1],center[0]-p[0])
                        angles=(np.arctan2(delta[:,1],delta[:,0])-ref+math.pi)%(2*math.pi)-math.pi
                        if np.ptp(angles)<math.radians(3):continue
                self.observe(p,ch,'search')
                self.seen.add((i,ch))
            self.done.add(i)
        certified=(len(self.cleared)==16 or (len(self.done)==len(self.stations) and not self.known))
        if not certified:
            raise RuntimeError('Missing stop certificate')
        self.c.exit()
        return dict(status='complete',cleared=sorted(self.cleared),metrics=self.c.metrics(),
                    stop_certificate=dict(kind='count16' if len(self.cleared)==16 else 'cell_halfplane_cover' if self.cfg['mesh_kind']=='compact' else 'triangular_halfplane_cover',
                        cover_sha256=cover_hash() if self.cfg['mesh_kind']=='compact' else None,
                        spacing=self.cfg['spacing'],mesh_kind=self.cfg['mesh_kind'],stations=self.stations.tolist(),triangles=self.triangles.tolist(),
                        completed_stations=sorted(self.done),scanned_pairs=len(self.seen)))

def run(client,config=None,log=lambda x:None):
    return Strategy(client,config or {},log).run()
