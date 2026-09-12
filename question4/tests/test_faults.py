import copy
import unittest
from question3.interface import Client, ProtocolError, TransportUncertain
from question4.simulator import Simulator
from question4.cases import make_case
from question4.strategy import run
from question4.audit import audit

CONFIG=dict(scheduling='route',mesh_kind='compact',scan_known='certified',centroid_route=True,known_count_stop=True)

class DropOnce:
    def __init__(self,env):self.env=env;self.dropped=False
    def request(self,path,payload,timeout):
        result=self.env.request(path,payload,timeout)
        if path=='/measure' and not self.dropped:
            self.dropped=True;raise ConnectionError('Injected lost accepted response')
        return result

class FaultTests(unittest.TestCase):
    def test_lost_accepted_response_is_retried_and_audited_once(self):
        case=make_case(72003,'tangent');records=[]
        c=Client(DropOnce(Simulator(case)),'SELF',records.append);r=run(c,CONFIG)
        self.assertEqual(c.counts['retries'],1)
        self.assertTrue(audit(case,records,r)['passed'])

    def test_rejected_request_retains_clock_and_poisoned_state(self):
        class Reject:
            def request(self,path,payload,timeout):return 200,dict(accepted=False,virtual_time_s=0)
        c=Client(Reject(),'SELF')
        with self.assertRaises(ProtocolError):c.enter()
        self.assertEqual(c.virtual,0)
        self.assertTrue(c.poisoned)

    def test_exhausted_retries_cannot_claim_completion(self):
        class Lost:
            def request(self,path,payload,timeout):raise ConnectionError('Injected disconnect')
        c=Client(Lost(),'SELF')
        with self.assertRaises(TransportUncertain):run(c,CONFIG)
        self.assertTrue(c.poisoned)

    def test_numerically_inconsistent_bearing_rejected(self):
        from question4.geometry import first_region,bearing_clip
        p=first_region((0,0),0)
        with self.assertRaises(RuntimeError):bearing_clip(p,(-10,0),180)

    def test_configuration_typo_rejected_before_enter(self):
        c=Client(Simulator(make_case(1)),'SELF')
        with self.assertRaises(ValueError):run(c,dict(mesh_knd='compact'))
        self.assertFalse(c.entered)

if __name__=='__main__':unittest.main()
