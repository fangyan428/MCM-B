"""Certified directional search; accepts only a public action client and fixed config."""
import math
import numpy as np
from .geometry import mesh, first_region, bearing_clip, optical_cover, estimate, bbox

DEFAULT = dict(spacing=990., search_order='nearest', scheduling='immediate',
               localization='pair', probe_width=300., opportunistic_clear=False,
               shared_scan=False, optical_order='snake')

class Strategy:
    def __init__(self, client, config, log=lambda x:None):
        self.c=client; self.cfg=DEFAULT|config; self.log=log
        self.stations,self.triangles=mesh(self.cfg['spacing'])
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
        if self.cfg['localization']=='pair':
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
        if radius<20-1e-5:
            if not self.clear(center,ch,'certified_clear'):
                raise RuntimeError('Certified clear failed')
            return
        points,r=optical_cover(poly,data['angle'],self.c.position)
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
            if self.known:
                ch=min(self.known,key=lambda c:math.dist(self.c.position,estimate(self.known[c]['poly'])[0]))
                self.localize(ch)
                continue
            if not remaining:
                break
            i=min(remaining,key=lambda j:(math.dist(self.c.position,self.stations[j]),j))
            p=self.stations[i]
            channels=[ch for ch in range(1,21) if ch not in self.cleared]
            if self.c.channel in channels:
                channels.remove(self.c.channel);channels.insert(0,self.c.channel)
            for ch in channels:
                self.observe(p,ch,'search')
                self.seen.add((i,ch))
            self.done.add(i)
        certified=(len(self.cleared)==16 or (len(self.done)==len(self.stations) and not self.known))
        if not certified:
            raise RuntimeError('Missing stop certificate')
        self.c.exit()
        return dict(status='complete',cleared=sorted(self.cleared),metrics=self.c.metrics(),
                    stop_certificate=dict(kind='count16' if len(self.cleared)==16 else 'triangular_halfplane_cover',
                        spacing=self.cfg['spacing'],stations=self.stations.tolist(),triangles=self.triangles.tolist(),
                        completed_stations=sorted(self.done),scanned_pairs=len(self.seen)))

def run(client,config=None,log=lambda x:None):
    return Strategy(client,config or {},log).run()
