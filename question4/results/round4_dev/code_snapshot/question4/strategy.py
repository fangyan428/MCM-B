"""Certified directional search; accepts only a public action client and fixed config."""
import math
import numpy as np
from .geometry import mesh, radial_mesh, first_region, bearing_clip, optical_cover, estimate, bbox
from .routing import tour

DEFAULT = dict(spacing=990., search_order='nearest', scheduling='immediate',
               localization='pair', probe_width=300., opportunistic_clear=False,
               shared_scan=False, optical_order='snake', refinement=False, joint_weight=1.,
               mesh_kind='lattice', scan_known='all')

class Strategy:
    def __init__(self, client, config, log=lambda x:None):
        self.c=client; self.cfg=DEFAULT|config; self.log=log
        self.stations,self.triangles=radial_mesh() if self.cfg['mesh_kind']=='radial' else mesh(self.cfg['spacing'])
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

    def localize(self,ch):
        data=self.known[ch]; poly=data['poly']; center,radius=estimate(poly)
        if radius<20-1e-5:
            if not self.clear(center,ch,'certified_clear'):
                raise RuntimeError('Certified clear failed')
            return
        if self.cfg['localization']=='pair' and len(self.readings[ch])<2:
            a=math.radians(data['angle']); v=np.array([-math.sin(a),math.cos(a)])
            candidates=[center+self.cfg['probe_width']*v,center-self.cfg['probe_width']*v]
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
            i=min(remaining,key=lambda j:(math.dist(self.c.position,self.stations[j]),j)) if remaining else None
            route_choice=None
            if self.cfg['scheduling']=='route':
                tasks=[('station',j,self.stations[j]) for j in remaining]+[('source',ch,estimate(data['poly'])[0]) for ch,data in self.known.items()]
                route_choice=tasks[tour(self.c.position,[t[2] for t in tasks])[0]]
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
                self.observe(p,ch,'search')
                self.seen.add((i,ch))
            self.done.add(i)
        certified=(len(self.cleared)==16 or (len(self.done)==len(self.stations) and not self.known))
        if not certified:
            raise RuntimeError('Missing stop certificate')
        self.c.exit()
        return dict(status='complete',cleared=sorted(self.cleared),metrics=self.c.metrics(),
                    stop_certificate=dict(kind='count16' if len(self.cleared)==16 else 'triangular_halfplane_cover',
                        spacing=self.cfg['spacing'],mesh_kind=self.cfg['mesh_kind'],stations=self.stations.tolist(),triangles=self.triangles.tolist(),
                        completed_stations=sorted(self.done),scanned_pairs=len(self.seen)))

def run(client,config=None,log=lambda x:None):
    return Strategy(client,config or {},log).run()
