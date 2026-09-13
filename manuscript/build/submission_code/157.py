import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from question3.cases import random_case
from question3.simulator import Simulator
from question3.self_server import make_server

class HttpCliTests(unittest.TestCase):
    def test_explicit_AB_over_real_http(self):
        env=Simulator(random_case(0));server=make_server(env)
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                out=Path(tmp)/'AB 演练'
                proc=subprocess.run([sys.executable,'-m','question3.run_http','--mode','self-http',
                    '--url',f'http://127.0.0.1:{server.server_port}',
                    '--config','question3/configs/round1/AB.json','--output',str(out)],capture_output=True,timeout=30)
                self.assertEqual(proc.returncode,0,proc.stderr.decode('utf-8',errors='replace'))
                r=json.loads((out/'result.json').read_text(encoding='utf-8'))
                self.assertEqual(r['status'],'complete')
                self.assertEqual(r['config']['modules'],dict(A=True,B=True,C=False))
                self.assertEqual(r['metrics']['virtual_time_s'],6429.685179)
                self.assertEqual(env.evaluation()['remaining_channels'],[])
                self.assertEqual(json.loads((out/'config.json').read_text(encoding='utf-8')),r['config'])
        finally:
            server.shutdown();server.server_close();worker.join()
    def test_rehearsal_requires_explicit_ui_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'must_not_exist'
            p=subprocess.run([sys.executable,'-m','question3.run_http','--mode','official-rehearsal',
                '--robot-id','TEST','--output',str(out)],capture_output=True,timeout=10)
            self.assertEqual(p.returncode,2);self.assertFalse(out.exists())
