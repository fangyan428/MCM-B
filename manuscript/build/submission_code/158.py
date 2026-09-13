"""Self HTTP only: preserve the old entry and replay the candidate's locked metrics."""
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


class InnovationHttpCliTests(unittest.TestCase):
    def test_original_and_candidate_match_frozen_metrics(self):
        root = Path(__file__).resolve().parents[1]
        expected = json.loads((root / 'innovation/package_smoke/bounded/summary.json').read_text(encoding='utf-8'))
        cases = {row['variant']: row for row in expected['rows'] if row['case_id'] == 'dev_0_spatial_hash'}
        for module, variant, extra in [
            ('question3.run_http', 'BASE', ['--config', str(root / 'configs/recommended_omni.json')]),
            ('question3.run_innovation_http', 'GATED_TOUR_MULTI_PARALLAX', []),
        ]:
            with self.subTest(variant=variant):
                env = Simulator(random_case(0))
                server = make_server(env)
                worker = threading.Thread(target=server.serve_forever, daemon=True)
                worker.start()
                try:
                    with tempfile.TemporaryDirectory() as tmp:
                        out = Path(tmp) / '自建接口结果'
                        proc = subprocess.run([
                            sys.executable, '-m', module, '--mode', 'self-http',
                            '--url', f'http://127.0.0.1:{server.server_port}', '--output', str(out), *extra,
                        ], cwd=root.parent, capture_output=True, timeout=30)
                        self.assertEqual(proc.returncode, 0, proc.stderr.decode('utf-8', errors='replace'))
                        result = json.loads((out / 'result.json').read_text(encoding='utf-8'))
                        self.assertEqual(result['status'], 'complete')
                        self.assertEqual(result['metrics'], cases[variant]['metrics'])
                        self.assertEqual(env.evaluation()['remaining_channels'], [])
                        self.assertTrue(result['exit_confirmed'])
                        self.assertIsNone(result['official_total'])
                        self.assertIsNone(result['clearance_ratio'])
                        if variant != 'BASE':
                            self.assertTrue((out / 'code_sha256.json').is_file())
                finally:
                    server.shutdown()
                    server.server_close()
                    worker.join()

    def test_candidate_requires_explicit_rehearsal_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'must_not_exist'
            proc = subprocess.run([
                sys.executable, '-m', 'question3.run_innovation_http', '--mode', 'official-rehearsal',
                '--robot-id', 'TEST', '--output', str(out),
            ], capture_output=True, timeout=10)
            self.assertEqual(proc.returncode, 2)
            self.assertFalse(out.exists())
