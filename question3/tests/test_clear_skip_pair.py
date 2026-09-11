"""Combined constraints are only proposals until their nonnegative witness passes."""
import unittest
import json
import tempfile
from pathlib import Path
import numpy as np
from question3.clear_skip import failure_certificate
from question3.cases import random_case
from question3.interface import Client,JsonlLog
from question3.simulator import Simulator
from question3.strategy import run
from question3.audit import audit_folder


class ClearSkipPairTests(unittest.TestCase):
    def test_corner_missed_by_each_edge_is_certified_by_pair(self):
        A=np.eye(2);b=np.zeros(2)
        self.assertIsNone(failure_certificate((15,15),(A,b)))
        proof=failure_certificate((15,15),(A,b),combine=True)
        self.assertIsNotNone(proof)
        w=np.array(proof['halfplane_weights']);self.assertTrue(np.all(w>=0));self.assertAlmostEqual(w.sum(),1)
        self.assertAlmostEqual(proof['separation_m'],15*np.sqrt(2))

    def test_tangent_and_uncertain_corner_are_retained(self):
        planes=(np.eye(2),np.zeros(2))
        for r in [0,19.99,20,20+1e-6]:
            self.assertIsNone(failure_certificate(np.ones(2)*r/np.sqrt(2),planes,combine=True))
        self.assertIsNotNone(failure_certificate(np.ones(2)*20.001/np.sqrt(2),planes,combine=True))

    def test_parallel_and_opposing_normals_fail_closed(self):
        for A,b,p in [(np.array([[1.,0.],[1.,0.]]),np.array([0.,1.]),(15.,15.)),
                      (np.array([[1.,0.],[-1.,0.]]),np.zeros(2),(0.,100.))]:
            self.assertIsNone(failure_certificate(p,(A,b),combine=True))

    def test_single_witness_is_exactly_preserved(self):
        planes=(np.eye(2),np.zeros(2))
        self.assertEqual(failure_certificate((30,15),planes),failure_certificate((30,15),planes,combine=True))

    def test_rotation_translation_and_valid_region_points(self):
        angle=.437;R=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
        origin=np.array([1e6,-1e6]);A=np.eye(2)@R.T;b=A@origin;p=origin+R@np.array([15.,15.])
        proof=failure_certificate(p,(A,b),combine=True);self.assertIsNotNone(proof)
        for x in np.linspace(-40,0,9):
            for y in np.linspace(-40,0,9):
                g=origin+R@np.array([x,y]);self.assertGreater(np.linalg.norm(g-p),20)
        self.assertIsNone(failure_certificate(origin-R@np.ones(2),(A,b),combine=True))

    def test_auditor_recomputes_weights_and_rejects_negative_weight(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);case=random_case(1)
            config=json.loads(Path('question3/configs/round12_dev/Q.json').read_text())
            actions=JsonlLog(folder/'actions.jsonl');events=JsonlLog(folder/'strategy.jsonl')
            r=run(Client(Simulator(case),'SELF',actions),config,events);actions.close();events.close()
            (folder/'evaluator_hidden_case.json').write_text(json.dumps(case))
            (folder/'result.json').write_text(json.dumps(dict(summary=dict(rounding='bounded'),strategy=r)))
            rows=list(map(json.loads,(folder/'strategy.jsonl').read_text().splitlines()))
            proof=next(e for e in rows if e['type']=='certified_clear_skip')
            # A single inequality is also a valid nonnegative-combination witness.
            k=proof.pop('halfplane_index');proof['halfplane_weights']=[float(i==k) for i in range(4)]
            path=folder/'strategy.jsonl';path.write_text('\n'.join(map(json.dumps,rows))+'\n')
            self.assertGreater(audit_folder(folder),0)
            proof['halfplane_weights'][(k+1)%4]=-.1
            path.write_text('\n'.join(map(json.dumps,rows))+'\n')
            with self.assertRaises(AssertionError):audit_folder(folder)
