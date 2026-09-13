import json
from pathlib import Path
import tempfile
import threading
import unittest
from question3.audit import audit_folder
from question3.cases import late_source_case
from question3.interface import Client,HttpTransport,JsonlLog
from question3.self_server import make_server
from question3.simulator import Simulator
from question3.strategy import run


def cfg(name):return json.loads(Path('question3/configs/round7_count',name+'.json').read_text())
def fixture(n=16,near=False):
    return dict(id='count_contract',seed=991,error_mode='positive',sources=[
        dict(channel=c,x=.1*c if near else 300+5*c,y=0.,radius=1000.) for c in range(1,n+1)])


class CountStopTests(unittest.TestCase):
    def test_sixteen_successes_stop_on_action_prefix(self):
        case=fixture(near=True);base_log=[];short_log=[]
        base=run(Client(Simulator(case),'SELF',base_log.append),cfg('REF'))
        env=Simulator(case);short=run(Client(env,'SELF',short_log.append),cfg('U'))
        def actions(log):return [(e['path'],e['payload'].get('position'),e['payload'].get('channel'))
            for e in log if e['type']=='request' and e['path'] in ('/measure','/clear')]
        before=actions(base_log);after=actions(short_log)
        self.assertEqual(before[:len(after)],after);self.assertLess(len(after),len(before))
        self.assertEqual(short['status'],'complete');self.assertFalse(env.evaluation()['remaining_channels'])
        self.assertEqual(short['stopping_certificate']['method'],'source_count_upper_bound')
        self.assertEqual(short['absent_channels'],[17,18,19,20])
        self.assertTrue(all(len(short['negative_station_ids'][str(c)])<7 for c in [17,18,19,20]))
        self.assertLess(short['metrics']['virtual_time_s'],base['metrics']['virtual_time_s'])

    def test_sixteen_detected_are_not_sixteen_cleared(self):
        class AlwaysFail(Client):
            def clear(self,p,c,phase='clear'):
                result=super().clear(p,c,phase)
                return {**result,'clear_result':'no_target_in_range'}
        events=[];r=run(AlwaysFail(Simulator(fixture()),'SELF'),cfg('K'),events.append)
        saturated=[e for e in events if e['type']=='source_upper_bound_saturated']
        self.assertEqual(len(saturated),1);self.assertEqual(len(saturated[0]['still_to_clear']),16)
        self.assertEqual(r['status'],'incomplete');self.assertFalse(r['exit_confirmed'])
        self.assertIsNone(r['stopping_certificate']);self.assertEqual(r['cleared_channels'],[])

    def test_fewer_than_sixteen_keep_coverage_and_late_source(self):
        for case in [fixture(15),late_source_case()]:
            before=run(Client(Simulator(case),'SELF'),cfg('REF'))
            for variant in ['U','K']:
                r=run(Client(Simulator(case),'SELF'),cfg(variant))
                self.assertEqual(r['metrics'],before['metrics']);self.assertEqual(r['status'],'complete')
                self.assertEqual(r['stopping_certificate']['method'],'seven_station_channel_cover')
                for c in r['absent_channels']:self.assertEqual(len(r['negative_station_ids'][str(c)]),7)
                if case['id']=='late_channel20_after_ten':self.assertIn(20,r['cleared_channels'])

    def test_deadline_after_discovery_cannot_complete(self):
        client=Client(Simulator(fixture()),'SELF');seen=[]
        def event(e):
            if e['type']=='source_upper_bound_saturated':seen.append(e);client.deadline=0
        r=run(client,cfg('DK'),event)
        self.assertTrue(seen);self.assertEqual(r['status'],'incomplete');self.assertFalse(r['exit_confirmed'])

    def test_last_success_retry_counts_distinct_channels_once(self):
        env=Simulator(fixture(near=True));dropped=False
        class DropLast:
            def request(self,path,body,timeout):
                nonlocal dropped
                response=env.request(path,body,timeout)
                if path=='/clear' and body['channel']==16 and not dropped:
                    dropped=True;raise OSError('last accepted clear response lost')
                return response
        r=run(Client(DropLast(),'SELF'),cfg('U'))
        self.assertTrue(dropped);self.assertEqual(r['status'],'complete')
        self.assertEqual(r['metrics']['counts']['clear_success'],16)
        self.assertEqual(r['metrics']['counts']['retries'],1)

    def test_auditor_rejects_forged_sixteen_certificate(self):
        case=fixture(15)
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);log=JsonlLog(folder/'actions.jsonl')
            r=run(Client(Simulator(case),'SELF',log),cfg('REF'));log.close()
            r['stopping_certificate']=dict(method='source_count_upper_bound',source_upper_bound=16,
                successful_channels=list(range(1,17)),inferred_absent_channels=list(range(17,21)))
            (folder/'evaluator_hidden_case.json').write_text(json.dumps(case))
            (folder/'result.json').write_text(json.dumps(dict(summary={'rounding':'bounded'},strategy=r)))
            with self.assertRaises(AssertionError):audit_folder(folder)

    def test_count_mode_real_self_http(self):
        env=Simulator(fixture());server=make_server(env)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            r=run(Client(HttpTransport(f'http://127.0.0.1:{server.server_port}'),'SELF'),cfg('DK'))
            self.assertEqual(r['status'],'complete');self.assertEqual(r['stopping_certificate']['method'],'source_count_upper_bound')
            self.assertFalse(env.evaluation()['remaining_channels'])
        finally:server.shutdown();server.server_close();thread.join()

    def test_unrecognized_bound_mode_before_enter(self):
        c=cfg('U');c['count_stop']='cleared_10';client=Client(Simulator(fixture()),'SELF')
        with self.assertRaises(ValueError):run(client,c)
        self.assertFalse(client.entered)
