"""Meaningful regression checks for exact public-response replay boundaries."""
import copy
from pathlib import Path
import tempfile
import unittest
from paper_evidence.q4_mechanism_reset_20260912.qa.replay import RecordedResponses,static_scan

ROOT=Path(__file__).parent

def request(identifier='old'):
    return {'type':'request','path':'/measure','payload':{'request_id':identifier,'robot_id':'SELF',
            'arena_id':'default','position':{'x':12.5,'y':-7.25},'channel':3},'attempt':0}

def response(identifier='old'):
    return {'type':'response','path':'/measure','request_id':identifier,'http_status':200,
            'response':{'accepted':True,'virtual_time_s':8.5,'real_timestamp_ms':123,'measure_result':'no_signal'}}

class Tests(unittest.TestCase):
    def test_exact_point_rejects_coordinate_change(self):
        req=request();trans=RecordedResponses([req,response()]);body=copy.deepcopy(req['payload'])
        body['position']['x']+=1e-8
        with self.assertRaisesRegex(AssertionError,'Public action mismatch'):trans.request('/measure',body)
        self.assertEqual(trans.progress,(0,1))

    def test_request_id_can_change_but_retry_must_reuse(self):
        req=request();retry=copy.deepcopy(req);retry['attempt']=1
        error={'type':'transport_error','request_id':'old','error':'recorded socket error'}
        trans=RecordedResponses([req,error,retry,response()]);body=copy.deepcopy(req['payload']);body['request_id']='new'
        with self.assertRaises(OSError):trans.request('/measure',body)
        wrong=body|{'request_id':'another'}
        with self.assertRaisesRegex(AssertionError,'retry changed'):trans.request('/measure',wrong)
        self.assertEqual(trans.request('/measure',body),(200,response()['response']))
        self.assertEqual(trans.progress,(2,2))

    def test_no_extra_actions(self):
        req=request();trans=RecordedResponses([req,response()]);trans.request('/measure',req['payload'])
        with self.assertRaisesRegex(AssertionError,'extra action'):trans.request('/measure',req['payload'])

    def test_static_scan_catches_evaluator_import_and_hidden_access(self):
        with tempfile.TemporaryDirectory(prefix='scan_test_',dir=ROOT) as temporary:
            folder=Path(temporary);(folder/'policy.py').write_text('from question4.simulator import Simulator\ndef f(c):\n return c.hidden["sources"]\n')
            report=static_scan('policy',folder)
            self.assertFalse(report['passed']);self.assertEqual(len(report['violations']),3)

    def test_policy_dependency_scan_passes_with_public_geometry_io_review(self):
        report=static_scan();self.assertTrue(report['passed']);self.assertGreater(len(report['modules']),10)
        self.assertTrue(report['manual_review_findings'])
        self.assertTrue(all('geometry' in r['module'] for r in report['manual_review_findings']))

if __name__=='__main__':unittest.main()
