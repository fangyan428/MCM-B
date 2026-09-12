"""Independent SELF-only Q4 scheduling mechanisms using public feedback only.

The policy imports public strategy/geometry code, never cases, Simulator, files,
random seeds, orientations or source positions. Scheduling predictions are cost
heuristics; the inherited enclosing-region/finite-grid clearing and station
coverage certificates remain the only completeness mechanisms.
"""
import math
import numpy as np

from question4.strategy import run as baseline_run
from question4.geometry import estimate, optical_cover
from question4.routing import tour
from question4.innovation.strategy import Strategy as Parent, BASELINE_CONFIG
from question4.innovation.geometry import proposals


CANDIDATES = {
    'ACTUAL_TASK': {'schedule': 'actual_task', 'schedule_parent': 'baseline'},
    'BACKBONE': {'schedule': 'backbone', 'schedule_parent': 'baseline'},
    'WINDOW': {'schedule': 'window', 'schedule_parent': 'baseline'},
    'BACKBONE_ADAPT': {'schedule': 'backbone', 'schedule_parent': 'adapt'},
}


class Strategy(Parent):
    def __init__(self, client, config=None, log=lambda row: None):
        config = config or {}
        if set(config) - {'schedule', 'schedule_parent'}:
            raise ValueError('Unknown scheduling configuration')
        self.schedule = config.get('schedule', 'actual_task')
        self.schedule_parent = config.get('schedule_parent', 'baseline')
        if self.schedule not in ('baseline', 'actual_task', 'backbone', 'window'):
            raise ValueError('Unknown schedule')
        if self.schedule_parent not in ('baseline', 'adapt'):
            raise ValueError('Unknown schedule_parent')
        options = ({'mechanism': 'parallax', 'sharing': 'gated'}
                   if self.schedule_parent == 'adapt'
                   else {'mechanism': 'pair', 'sharing': 'off'})
        super().__init__(client, options, log)
        self.backbone = tour((0., 0.), self.stations.tolist())
        self.window_queue = []
        self.window_draining = False

    def scan_worthwhile(self, ch, p):
        """The original low-information rule, also used as a cost forecast."""
        if ch in self.cleared:
            return False
        if ch not in self.known:
            return True
        poly = self.known[ch]['poly']
        center, radius = estimate(poly)
        if radius < 20-1e-5:
            return False
        delta = poly-p
        ref = math.atan2(center[1]-p[1], center[0]-p[0])
        angles = (np.arctan2(delta[:, 1], delta[:, 0])-ref+math.pi) % (2*math.pi)-math.pi
        return np.ptp(angles) >= math.radians(3)

    def scan(self, index):
        p = self.stations[index]
        channels = [ch for ch in range(1, 21) if ch not in self.cleared]
        if self.c.channel in channels:
            channels.remove(self.c.channel)
            channels.insert(0, self.c.channel)
        for ch in channels:
            if self.scan_worthwhile(ch, p):
                self.observe(p, ch, 'search')
                self.seen.add((index, ch))
        self.done.add(index)

    def descriptor(self, ch):
        """Possible first actual action points and a heuristic completion point.

        A predicted exit is NOT a certificate. The actual parent localization
        executes until certified clear/finite-cover success, then we replan.
        """
        data = self.known[ch]
        center, radius = estimate(data['poly'])
        endpoint = self.target(data)
        if radius < 20-1e-5:
            return [center], center
        if self.schedule_parent == 'adapt':
            candidates = proposals(data['poly'], data['angle'], self.c.position, 'parallax')
            candidates = [p for p in candidates if tuple(p) not in self.visited.get(ch, set())]
            if candidates:
                return candidates, endpoint
        elif len(self.readings[ch]) < 2:
            a = math.radians(data['angle'])
            normal = np.array([-math.sin(a), math.cos(a)])
            return [center+self.cfg['probe_width']*normal,
                    center-self.cfg['probe_width']*normal], endpoint
        points, _ = optical_cover(data['poly'], data['angle'], self.c.position)
        # Original optical traversal chooses one of its two ends as entry.
        return [np.asarray(points[0]), np.asarray(points[-1])], endpoint

    def actual_task_choice(self, remaining):
        """Open directed service tour, accounting for service entry and exit."""
        tasks = [('station', index) for index in remaining] + [('source', ch) for ch in sorted(self.known)]
        entries, exits = [], []
        for kind, key in tasks:
            if kind == 'station':
                p = self.stations[key]
                entries.append([p]); exits.append(p)
            else:
                a, b = self.descriptor(key)
                entries.append(a); exits.append(b)
        entries = [np.asarray(a, dtype=float) for a in entries]
        exits = np.asarray(exits, dtype=float)
        # To predict the parent's entry choice, first select nearest entry from
        # the predecessor, then pay the entry->predicted-exit internal travel.
        transition = np.zeros((len(tasks)+1, len(tasks)), dtype=float)
        for i, prev in enumerate([np.asarray(self.c.position), *exits]):
            for j, points in enumerate(entries):
                distances = np.linalg.norm(points-prev, axis=1)
                k = int(np.argmin(distances))
                transition[i, j] = distances[k]+np.linalg.norm(points[k]-exits[j])
        order, unused, prev = [], set(range(len(tasks))), 0
        while unused:
            j = min(unused, key=lambda j: (transition[prev, j], j))
            order.append(j); unused.remove(j); prev = j+1

        def cost(path):
            return float(transition[0, path[0]]+sum(transition[a+1, b] for a, b in zip(path, path[1:])))

        # Directed edge costs require recalculating reversed internal edges.
        # Fixed effort limit is shared by all cases; no case-specific tuning.
        for _ in range(8):
            best, changed = cost(order), None
            for i in range(len(order)-1):
                for j in range(i+1, len(order)):
                    candidate = order[:i]+list(reversed(order[i:j+1]))+order[j+1:]
                    value = cost(candidate)
                    if value < best-1e-8:
                        best, changed = value, candidate
            if changed is None:
                break
            order = changed
        selected = tasks[order[0]]
        self.log(dict(event='actual_task_plan', selected=selected,
                      predicted_distance_m=cost(order),
                      order=[tasks[j] for j in order], prediction_is_certificate=False))
        return selected

    def backbone_choice(self, remaining):
        """Protect station discovery order and insert sources at minimum cost."""
        route = [index for index in self.backbone if index in remaining]
        if not route:
            points = [self.target(self.known[ch]) for ch in sorted(self.known)]
            channels = sorted(self.known)
            return 'source', channels[tour(self.c.position, points)[0]]
        sites = [np.asarray(self.c.position)]+[self.stations[index] for index in route]
        best = None
        for ch in sorted(self.known):
            target = self.target(self.known[ch])
            # Waiting for a station only costs a detection if the original
            # public polygon-based rule would actually scan this channel.
            waiting = 0.
            alternatives = []
            for slot in range(len(route)+1):
                prev = sites[slot]
                delta = math.dist(prev, target)
                if slot < len(route):
                    nxt = sites[slot+1]
                    delta += math.dist(target, nxt)-math.dist(prev, nxt)
                alternatives.append(delta/5+waiting)
                if slot < len(route) and self.scan_worthwhile(ch, sites[slot+1]):
                    waiting += 6.
            slot = min(range(len(alternatives)), key=lambda i: (alternatives[i], i))
            self.log(dict(event='backbone_insertion', channel=ch, best_slot=slot,
                          predicted_cost_s=alternatives[slot], immediate_cost_s=alternatives[0]))
            if slot == 0:
                candidate = (alternatives[0], ch)
                if best is None or candidate < best:
                    best = candidate
        if best is not None:
            return 'source', best[1]
        return 'station', route[0]

    def window_choice(self, remaining):
        """Collect two scheduled bearings before draining a source batch."""
        if self.window_draining and self.known:
            channels = sorted(self.known)
            order = tour(self.c.position, [self.target(self.known[ch]) for ch in channels])
            return 'source', channels[order[0]]
        if self.window_draining:
            self.window_draining = False
        if not self.window_queue:
            order = tour(self.c.position, [self.stations[index] for index in remaining])
            self.window_queue = [remaining[j] for j in order[:2]]
            self.log(dict(event='paired_discovery_window', stations=self.window_queue.copy()))
        index = self.window_queue.pop(0)
        if not self.window_queue:
            self.window_draining = True
        return 'station', index

    def run(self):
        if self.schedule == 'baseline':
            return super().run()
        self.c.enter()
        while len(self.done) < len(self.stations) or self.known:
            if len(self.cleared) == 16:
                break
            remaining = [i for i in range(len(self.stations)) if i not in self.done]
            if len(self.cleared)+len(self.known) == 16:
                remaining = []
            if not remaining:
                if not self.known:
                    break
                channels = sorted(self.known)
                order = tour(self.c.position, [self.target(self.known[ch]) for ch in channels])
                kind, key = 'source', channels[order[0]]
            elif self.schedule == 'actual_task':
                kind, key = self.actual_task_choice(remaining)
            elif self.schedule == 'backbone':
                kind, key = self.backbone_choice(remaining)
            else:
                kind, key = self.window_choice(remaining)
            if kind == 'source':
                self.localize(key)
            else:
                self.scan(key)
        certified = len(self.cleared) == 16 or (len(self.done) == len(self.stations) and not self.known)
        if not certified:
            raise RuntimeError('Missing stop certificate')
        self.c.exit()
        return dict(status='complete', cleared=sorted(self.cleared), metrics=self.c.metrics(),
                    stop_certificate=dict(kind='count16' if len(self.cleared) == 16 else 'triangular_halfplane_cover',
                        cover_sha256=None, spacing=self.cfg['spacing'], mesh_kind=self.cfg['mesh_kind'],
                        stations=self.stations.tolist(), triangles=self.triangles.tolist(),
                        completed_stations=sorted(self.done), scanned_pairs=len(self.seen)))


def run(client, config=None, log=lambda row: None):
    config = config or {}
    if config == {'schedule': 'baseline', 'schedule_parent': 'baseline'}:
        return baseline_run(client, BASELINE_CONFIG, log)
    return Strategy(client, config, log).run()
