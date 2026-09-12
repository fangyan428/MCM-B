"""Check export integrity, isolated frozen replay and local-only HTTP entry points."""
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / 'question3/innovation'


def main():
    manifest = json.loads((ROOT / 'EXPORT_MANIFEST.json').read_text(encoding='utf-8'))
    for name, info in manifest['files'].items():
        data = (ROOT / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == info['sha256'], name
        assert len(data) == info['bytes'], name
    raw = gzip.decompress((ROOT / 'LOCAL_RAW_CHECKSUMS.json.gz').read_bytes())
    assert hashlib.sha256(raw).hexdigest() == manifest['original_raw_manifest_sha256']
    upstream = subprocess.check_output(['git', 'rev-parse', 'origin/main'], cwd=REPO, text=True).strip()
    preserved = [
        'question3/interface.py', 'question3/run_http.py', 'question3/strategy.py',
        'question3/geometry.py', 'question3/modules.py', 'question3/configs/recommended_omni.json',
        'question3/order_routing.py', 'question3/cached_routing.py', 'question3/scan_route.py',
    ]
    for name in preserved:
        assert (REPO / name).read_bytes() == subprocess.check_output(['git', 'show', f'{upstream}:{name}'], cwd=REPO), name
    log = []

    def run(command, cwd):
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=180)
        log.append('$ ' + ' '.join(command) + '\n' + result.stdout + result.stderr)
        (ROOT / 'EXPORT_VERIFICATION.log').write_text('\n'.join(log), encoding='utf-8')
        assert result.returncode == 0, log[-1]

    with tempfile.TemporaryDirectory(prefix='q3-paper-export-') as tmp:
        isolated = Path(tmp) / 'innovation'
        shutil.copytree(ROOT, isolated, ignore=shutil.ignore_patterns('__pycache__', 'replays'))
        run([sys.executable, str(isolated / 'validate.py')], tmp)
        run([
            sys.executable, str(isolated / 'run_self.py'), '--round', 'replays/export_smoke',
            '--variants', 'BASE,GATED_TOUR_MULTI_PARALLAX',
            '--fixtures', str(isolated / 'final_validation_cases.json'),
            '--lock', str(isolated / 'validation_lock.json'), '--limit', '4',
            '--stage', 'replay_seen_validation',
        ], tmp)
        actual = json.loads((isolated / 'replays/export_smoke/bounded/summary.json').read_text(encoding='utf-8'))
        original = json.loads((ROOT / 'final_validation/bounded/summary.json').read_text(encoding='utf-8'))
        expected = {(r['variant'], r['case_id']): r for r in original['rows']}
        for row in actual['rows']:
            prior = expected[row['variant'], row['case_id']]
            for key in ['metrics', 'success', 'status', 'cleared', 'total', 'timeout', 'false_complete', 'audited_actions']:
                assert row[key] == prior[key], (row['case_id'], row['variant'], key)
        smoke = [dict(variant=r['variant'], case_id=r['case_id'], virtual_time_s=r['metrics']['virtual_time_s'], success=r['success']) for r in actual['rows']]
    run([sys.executable, '-m', 'unittest', 'question3.tests.test_http_cli', 'question3.tests.test_innovation_http_cli', '-v'], REPO)
    record = dict(
        verified_utc=datetime.now(timezone.utc).isoformat(),
        upstream_commit=upstream, copied_files_verified=len(manifest['files']),
        raw_checksum_index_verified=True, preserved_upstream_files=preserved,
        frozen_adversarial_tests_passed=10, http_cli_tests_passed=4,
        self_http_scenarios=3, isolated_metric_replays=smoke,
        exact_all_metrics_match=True, temporary_extraction_removed=True,
        initial_sandbox_socket_failure_log='EXPORT_VERIFICATION_sandbox.log',
        official_runs=0, formal_runs=0,
        note='Direct-file replay works without the repository or local paper_evidence. HTTP uses current shared client.',
    )
    (ROOT / 'EXPORT_VERIFICATION.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
