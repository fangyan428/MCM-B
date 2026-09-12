"""Freeze selection and complete independent design without generating a layout."""
import argparse
import hashlib
import json
import time
from pathlib import Path
from .experiment import source_hashes, canonical_sha256, write_json, FAMILIES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('configs', 'selection', 'output'):
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--count', type=int, required=True)
    parser.add_argument('--error-modes', default='spatial_hash,positive,negative,smooth')
    parser.add_argument('--roundings', default='bounded,pre_round_stress')
    parser.add_argument('--evidence', nargs='+', required=True)
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    configs = json.loads(Path(args.configs).read_text())
    selection = Path(args.selection).read_bytes()
    hashes = source_hashes()
    evidence = {}
    for folder in args.evidence:
        for name in ('lock.json', 'summary.json', 'comparison.json', 'integrity.json'):
            path = Path(folder)/name
            evidence[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    lock = dict(schema_version=1, stage='selection_lock_without_generation', created_unix=time.time(),
                configs=configs, configs_sha256=canonical_sha256(configs),
                code_sha256=hashes, code_bundle_sha256=canonical_sha256(hashes),
                reference='BASE', selection_sha256=hashlib.sha256(selection).hexdigest(),
                generator_seed=args.seed, generator_count=args.count, families=list(FAMILIES),
                error_modes=args.error_modes.split(','), roundings=args.roundings.split(','),
                failure_penalty_s=360000., evidence_sha256=evidence)
    write_json(out/'lock.json', lock)
    (out/'selection_snapshot.txt').write_bytes(selection)
    write_json(out/'configs.json', configs)
    print(json.dumps(dict(output=str(out), code_bundle_sha256=lock['code_bundle_sha256'],
                          layouts_generated=0, design_layouts=args.count)))


if __name__ == '__main__':
    main()
