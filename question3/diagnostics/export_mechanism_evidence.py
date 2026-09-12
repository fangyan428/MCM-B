"""Export the locally frozen Q3 experiment into Git without per-case raw traces.

No simulation is started. Runtime bytes and the validation lock remain unchanged.
"""
import gzip
import hashlib
import json
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / 'paper_evidence/q3_mechanism_reset_20260912'
DEST = REPO / 'question3/innovation'


def main():
    DEST.mkdir(exist_ok=False)
    manifest = {}

    def copy(path):
        rel = path.relative_to(SOURCE)
        target = DEST / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert hashlib.sha256(target.read_bytes()).hexdigest() == digest
        manifest[str(rel)] = dict(source=str(path.relative_to(REPO)), sha256=digest,
                                  bytes=path.stat().st_size)

    lock = json.loads((SOURCE / 'validation_lock.json').read_text())
    for name, digest in lock['code_sha256'].items():
        assert hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() == digest
        copy(SOURCE / name)
    for path in (SOURCE / 'frozen').rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts:
            copy(path)
    for path in SOURCE.iterdir():
        if not path.is_file() or path.name in {'ARTIFACT_SHA256.json', 'README.md', 'REPRODUCE.md'}:
            continue
        if path.suffix in {'.md', '.json', '.csv', '.png', '.svg'} or path.name in {
            'analyze_final.py', 'deliver.py', 'test_adversarial.py',
            'adversarial_tests_selected.log', 'public_transcript_replay.json',
            'package_smoke.log', 'self_http_check_retry.log', 'final_analysis.log',
            'best_candidate_package.zip.sha256',
        }:
            if str(path.relative_to(SOURCE)) not in manifest:
                copy(path)
    for directory in SOURCE.iterdir():
        if not directory.is_dir() or directory.name in {'frozen', '__pycache__', 'self_http', 'source_review'}:
            continue
        for name in ['README.md', 'REVIEW.md']:
            if (directory / name).is_file():
                copy(directory / name)
        for batch in directory.iterdir():
            if not batch.is_dir() or not (batch / 'summary.json').is_file():
                continue
            for name in ['summary.json', 'comparison.json', 'configs.json', 'metadata.json', 'code_sha256.json']:
                if (batch / name).is_file():
                    copy(batch / name)
            snapshot = batch / 'code_snapshot'
            if snapshot.exists():
                for path in snapshot.rglob('*.py'):
                    copy(path)
    raw = SOURCE / 'ARTIFACT_SHA256.json'
    with (DEST / 'LOCAL_RAW_CHECKSUMS.json.gz').open('wb') as stream:
        with gzip.GzipFile(fileobj=stream, mode='wb', filename='', mtime=0) as archive:
            archive.write(raw.read_bytes())
    metadata = dict(
        original_evidence_root=str(SOURCE.relative_to(REPO)),
        original_raw_manifest_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
        runtime_and_validation_lock_byte_identical=True,
        per_case_raw_traces_included=False, original_recommendation_changed=False,
        files=manifest,
    )
    (DEST / 'EXPORT_MANIFEST.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    print(json.dumps(dict(files=len(manifest), bytes=sum(v['bytes'] for v in manifest.values())), indent=2))


if __name__ == '__main__':
    main()
