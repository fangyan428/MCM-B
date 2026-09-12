"""Experimental mechanisms with a frozen Q4 public-feedback policy as parent.

No truth, files, random seeds, source types, radii or orientations are accessed.
The 25-station discovery and finite optical fallback certificates are retained.
"""
import math
import numpy as np
from question4.strategy import Strategy as Baseline, run as baseline_run
from question4.geometry import estimate, optical_cover
from .geometry import proposals, conditional_worthwhile, contains, optical_order

BASELINE_CONFIG = dict(scheduling='route', mesh_kind='radial', scan_known='certified',
                       centroid_route=True, known_count_stop=True, scan_information=True)
DEFAULT = dict(mechanism='pair', sharing='off', adaptive_steps=8,
               share_after_clear=True, adaptive_gate=False, optical_order='original',
               shadow_skip=False, blind_clear=False)


class Strategy(Baseline):
    def __init__(self, client, config, log=lambda row: None):
        extras = {k: v for k, v in config.items() if k != 'baseline_config'}
        if set(extras)-set(DEFAULT):
            raise ValueError('Unknown innovation config: '+str(set(extras)-set(DEFAULT)))
        self.options = DEFAULT | extras
        if self.options['mechanism'] not in ('pair', 'center', 'parallax'):
            raise ValueError('Unknown localization mechanism')
        if self.options['sharing'] not in ('off', 'range', 'gated'):
            raise ValueError('Unknown sharing mechanism')
        if self.options['optical_order'] not in ('original', 'nearest_branch'):
            raise ValueError('Unknown optical order')
        for key in ('share_after_clear', 'adaptive_gate', 'shadow_skip', 'blind_clear'):
            if not isinstance(self.options[key], bool):
                raise ValueError('Invalid boolean '+key)
        if not isinstance(self.options['adaptive_steps'], int) or not 1 <= self.options['adaptive_steps'] <= 16:
            raise ValueError('Invalid finite step bound')
        super().__init__(client, config.get('baseline_config', BASELINE_CONFIG), log)
        self.visited = {}
        self._in_shared = False

    def observe(self, p, ch, phase):
        before = tuple(self.c.position)
        old = self.known[ch]['poly'].copy() if ch in self.known else None
        kind = super().observe(p, ch, phase)
        self.visited.setdefault(ch, set()).add(tuple(map(float, p)))
        if kind == 'no_signal' and old is not None:
            assert np.array_equal(old, self.known[ch]['poly'])
        if ch in self.known:
            self.log(dict(event='feasible_region', channel=int(ch), kind=kind,
                          vertices=self.known[ch]['poly'].tolist(), point=list(p)))
        if phase != 'search' and not self._in_shared and math.dist(before, self.c.position) > 1e-6:
            self.share(ch)
        return kind

    def clear(self, p, ch, phase):
        before = tuple(self.c.position)
        ok = super().clear(p, ch, phase)
        if (phase != 'near' and self.options['share_after_clear'] and not self._in_shared
                and math.dist(before, self.c.position) > 1e-6):
            self.share(ch)
        return ok

    def share(self, active):
        mode = self.options['sharing']
        if mode == 'off':
            return
        self._in_shared = True
        try:
            p = np.asarray(self.c.position)
            for ch in sorted(set(self.known)-{active}):
                if tuple(p) in self.visited.get(ch, set()):
                    continue
                poly = self.known[ch]['poly']
                _, radius = estimate(poly)
                # Q3's distance condition is used ONLY as a cost screen. No
                # assumption that the source faces this point follows from it.
                if radius < 20-1e-5 or np.linalg.norm(poly-p, axis=1).max() >= 1000-1e-5:
                    continue
                if mode == 'gated' and not conditional_worthwhile(poly, p):
                    self.log(dict(event='conditional_gate_skip', channel=int(ch), point=p.tolist()))
                    continue
                if self.options['shadow_skip']:
                    from .reception import shadow_certificate
                    certificate = shadow_certificate(poly, [a for a, _ in self.readings[ch]],
                                                     self.missed.get(ch, []), p)
                    if certificate is not None:
                        self.log(dict(event='directional_shadow_skip', channel=int(ch), point=p.tolist(),
                                      vertices=poly.tolist(), certificate=certificate))
                        continue
                self.log(dict(event='shared_attempt', channel=int(ch), point=p.tolist(),
                              reception_guaranteed=False, conditional_gate=mode == 'gated'))
                self.observe(p, ch, 'shared_localization')
        finally:
            self._in_shared = False

    def optical_fallback(self, ch):
        data = self.known[ch]
        poly = data['poly']; center, radius = estimate(poly)
        if radius < 20-1e-5:
            self.log(dict(event='certified_clear', channel=int(ch), point=center.tolist(),
                          radius=radius, vertices=poly.tolist()))
            if not self.clear(center, ch, 'certified_clear'):
                raise RuntimeError('Certified clear failed')
            return
        points, radius = optical_cover(poly, data['angle'], self.c.position)
        self.log(dict(event='optical_cover', channel=int(ch), vertices=poly.tolist(),
                      cover_radius=radius, points=len(points), angle=data['angle']))
        order = optical_order(points, self.c.position, self.options['optical_order'])
        self.log(dict(event='optical_route', channel=int(ch), order=order,
                      start=list(self.c.position), method=self.options['optical_order']))
        for j, index in enumerate(order):
            p = points[index]
            self.log(dict(event='optical_step', channel=int(ch), entry=j == 0,
                          point=list(p), movement_s=math.dist(self.c.position, p)/5))
            if self.clear(p, ch, 'optical_fallback'):
                return
        raise RuntimeError('Exhausted optical certificate without success')

    def localize(self, ch):
        mode = self.options['mechanism']
        if mode == 'pair':
            if self.options['optical_order'] == 'original':
                return super().localize(ch)
            # Preserve the fixed-pair measurement policy; only optical ordering
            # differs from the frozen parent. Baseline refinement is not used.
            if self.cfg['refinement'] or self.cfg['opportunistic_clear']:
                raise ValueError('Optical-order ablation requires unmodified pair parent')
            data = self.known[ch]; center, radius = estimate(data['poly'])
            if self.cfg['localization'] == 'pair' and radius >= 20-1e-5 and len(self.readings[ch]) < 2:
                a = math.radians(data['angle']); side = np.array([-math.sin(a), math.cos(a)])
                center = self.target(data) if self.cfg['centroid_probe'] else center
                points = sorted([center+self.cfg['probe_width']*side, center-self.cfg['probe_width']*side],
                                key=lambda p: math.dist(self.c.position, p))
                for p in points:
                    self.observe(p, ch, 'localize')
                    if ch in self.cleared:
                        return
                    if len(self.readings[ch]) >= 2:
                        break
            return self.optical_fallback(ch)
        for step in range(self.options['adaptive_steps']):
            data = self.known[ch]; poly = data['poly']
            center, radius = estimate(poly)
            if radius < 20-1e-5:
                break
            points = proposals(poly, data['angle'], self.c.position, mode)
            found = False
            for p in points:
                if tuple(p) in self.visited.get(ch, set()):
                    continue
                if self.options['adaptive_gate'] and not conditional_worthwhile(poly, p):
                    continue
                self.log(dict(event='adaptive_attempt', channel=int(ch), step=step,
                              point=p.tolist(), radius=radius, reception_guaranteed=False))
                kind = self.observe(p, ch, 'adaptive_localization')
                if ch in self.cleared:
                    return
                if kind == 'direction':
                    found = True
                    break
                if self.options['blind_clear'] and contains(self.known[ch]['poly'], p):
                    # Radio has already paid for this movement. A 3-second
                    # optical attempt can succeed on the blind side, even near.
                    self.log(dict(event='blind_optical_attempt', channel=int(ch), point=list(p)))
                    if self.clear(p, ch, 'blind_optical_attempt'):
                        return
            if not found or estimate(self.known[ch]['poly'])[1] > radius*.9:
                break
        self.optical_fallback(ch)


def run(client, config=None, log=lambda row: None):
    config = config or {}
    if config.get('mechanism') == 'baseline':
        if set(config)-{'mechanism', 'baseline_config'}:
            raise ValueError('Baseline must not contain experimental options')
        return baseline_run(client, config.get('baseline_config', BASELINE_CONFIG), log)
    return Strategy(client, config, log).run()
