import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from question3.self_server import make_server
from question4.audit import check_cover
from question4.cases import make_case
from question4.simulator import Simulator

class CoverHttpTests(unittest.TestCase):
    def test_continuous_cover_and_missing_cell(self):
        contents=Path('question4/certificates/compact22.json').read_bytes()
        self.assertEqual(len(check_cover(contents)),22)
        data=json.loads(contents);data['leaves'].pop()
        with self.assertRaises(AssertionError):check_cover(json.dumps(data).encode())

    def test_bad_witness_and_station(self):
        data=json.loads(Path('question4/certificates/compact22.json').read_bytes())
        bad=copy.deepcopy(data)
        leaf=next(x for x in bad['leaves'] if not x.get('outside'));leaf['witnesses']=[0,1,2]
        with self.assertRaises(AssertionError):check_cover(json.dumps(bad).encode())
        bad=copy.deepcopy(data);bad['stations'][0]=[1e5,1e5]
        with self.assertRaises(AssertionError):check_cover(json.dumps(bad).encode())

    def test_recommended_mechanisms_over_real_http(self):
        env=Simulator(make_case(81001,'outward'));server=make_server(env)
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                out=Path(tmp)/'run'
                proc=subprocess.run([sys.executable,'-m','question4.run_http',
                    '--url',f'http://127.0.0.1:{server.server_port}','--output',str(out)],capture_output=True,timeout=40)
                self.assertEqual(proc.returncode,0,proc.stderr.decode())
                r=json.loads((out/'result.json').read_text());self.assertEqual(r['status'],'complete')
                self.assertEqual(env.evaluation()['remaining_channels'],[])
                self.assertIsNone(r['official_total'])
        finally:
            server.shutdown();server.server_close();worker.join()

    def test_official_mode_requires_actual_operator_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'must_not_exist'
            p=subprocess.run([sys.executable,'-m','question4.run_http','--mode','official-rehearsal','--output',str(out)],capture_output=True)
            self.assertEqual(p.returncode,2);self.assertFalse(out.exists())

if __name__=='__main__':unittest.main()
