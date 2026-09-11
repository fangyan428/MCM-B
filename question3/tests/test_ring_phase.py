"""Rotation invariant coverage, once-only evidence handling, and failure paths."""
import json
import math
from pathlib import Path
import tempfile
import unittest
import numpy as np
from question3.geometry import stations,station_cover_bound
from question3.ring_phase import align_first_entry
from question3.cases import random_case,late_source_case,clustered_case,boundary_case
from question3.interface import Client,JsonlLog
from question3.simulator import Simulator
from question3.strategy import run
from question3.audit import audit_folder


def config(name='PHASE'):
    return json.loads(Path('question3/configs/round14_dev',name+'.json').read_text())


class RingPhaseTests(unittest.TestCase):
    def test_radial_alignment_attains_continuous_entry_minimum(self):
        for p in [(0.,0.),(984.,-462.),(-100.,-2000.),(1125.,0.)]:
            for i in range(1,7):
                cover,phase=align_first_entry(stations(1125),i,p)
                self.assertAlmostEqual(math.dist(p,cover[i]),abs(math.hypot(*p)-1125),places=8)
                self.assertEqual(cover[0],(0.,0.));self.assertTrue(math.isfinite(phase))

    def test_rotated_boundary_coverage_retains_strict_margin(self):
        bound=station_cover_bound(1125);self.assertLess(bound,1000)
        for phase in [-8.7,-.31,0,1.73,12.4]:
            cover=np.array(stations(1125,phase))
            for radius in [0,900,1800]:
                for theta in np.linspace(0,2*math.pi,721)+phase:
                    p=radius*np.array([math.cos(theta),math.sin(theta)])
                    self.assertLessEqual(np.linalg.norm(cover-p,axis=1).min(),bound+1e-7)

    def test_shift_occurs_once_before_any_outer_search_evidence(self):
        records=[];events=[];client=Client(Simulator(random_case(0)),'SELF',records.append)
        def event(e):
            events.append(e)
            if e['type']=='ring_phase_selected':
                self.assertEqual(e['visited_before'],[0])
                self.assertEqual(events[-2]['type'],'schedule');self.assertEqual(events[-2]['task'],'scan')
                for r in records:
                    if r['type']=='request' and r['path']=='/measure' and r['phase']=='search':
                        self.assertEqual(r['payload']['position'],dict(x=0.,y=0.))
        result=run(client,config(),event)
        self.assertEqual(result['status'],'complete')
        self.assertEqual(sum(e['type']=='ring_phase_selected' for e in events),1)
        cover={tuple(p) for p in result['station_positions']}
        for r in records:
            if r['type']=='request' and r['path']=='/measure' and r['phase']=='search':
                self.assertIn(tuple(r['payload']['position'][k] for k in ['x','y']),cover)

    def test_late_channel_still_requires_complete_certificate(self):
        r=run(Client(Simulator(late_source_case()),'SELF'),config())
        self.assertEqual(r['status'],'complete');self.assertIn(20,r['cleared_channels'])
        self.assertEqual(r['stopping_certificate']['method'],'seven_station_channel_cover')

    def test_no_outer_scan_does_not_invent_phase_event(self):
        case=dict(id='all_near_16',seed=14,error_mode='spatial_hash',
                  sources=[dict(channel=c,x=c/10,y=0,radius=1000) for c in range(1,17)])
        events=[];r=run(Client(Simulator(case),'SELF'),config(),events.append)
        self.assertEqual(r['status'],'complete')
        self.assertFalse(any(e['type']=='ring_phase_selected' for e in events));self.assertNotIn('station_phase_rad',r)

    def test_deadline_after_phase_selection_is_incomplete(self):
        client=Client(Simulator(random_case(0)),'SELF');seen=[]
        def event(e):
            if e['type']=='ring_phase_selected':seen.append(e);client.deadline=0
        r=run(client,config(),event)
        self.assertTrue(seen);self.assertEqual(r['status'],'incomplete');self.assertFalse(r['exit_confirmed'])

    def test_empty_origin_makes_the_entire_policy_a_no_op(self):
        for case in [clustered_case(),boundary_case()]:
            a=run(Client(Simulator(case),'SELF'),config('REF'))
            events=[];b=run(Client(Simulator(case),'SELF'),config(),events.append)
            phases=[e for e in events if e['type']=='ring_phase_selected']
            self.assertEqual(len(phases),1);self.assertEqual(phases[0]['phase_rad'],0)
            self.assertEqual(phases[0]['position'],(0.,0.))
            self.assertEqual(a['metrics'],b['metrics']);self.assertEqual(a['station_positions'],b['station_positions'])

    def test_auditor_rejects_forged_station_phase(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);case=random_case(0)
            actions=JsonlLog(folder/'actions.jsonl');events=JsonlLog(folder/'strategy.jsonl')
            r=run(Client(Simulator(case),'SELF',actions),config(),events);actions.close();events.close()
            (folder/'evaluator_hidden_case.json').write_text(json.dumps(case))
            document=dict(summary=dict(rounding='bounded'),strategy=r)
            path=folder/'result.json';path.write_text(json.dumps(document));self.assertGreater(audit_folder(folder),0)
            r['station_phase_rad']+=.1;path.write_text(json.dumps(document))
            with self.assertRaises(AssertionError):audit_folder(folder)

    def test_invalid_phase_mode_or_nonjoint_before_enter(self):
        for c in [{**config(),'ring_phase':'always'},{**config(),'modules':{**config()['modules'],'B':False}}]:
            client=Client(Simulator(random_case(0)),'SELF')
            with self.assertRaises(ValueError):run(client,c)
            self.assertFalse(client.entered)
