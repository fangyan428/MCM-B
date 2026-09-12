"""Frozen, paired Q4 SELF experiments; never invokes an HTTP/official environment.

From the project root::

    python -m question4.innovation.experiment --configs path/to/configs.json \
        --output question4/innovation/results/dev --seed 940000 --count 24 \
        --error-modes spatial_hash,positive,negative,smooth \
        --roundings bounded,pre_round_stress --workers 4 --stage development

    python -m question4.innovation.experiment --configs path/to/selected.json \
        --selection path/to/selection.json --output path/to/locked_dev \
        --seed 950000 --count 6 --stage selection_lock

    python -m question4.innovation.experiment --configs path/to/selected.json \
        --selection path/to/selection.json --output path/to/validation \
        --seed 960000 --count 96 --lock path/to/locked_dev/lock.json \
        --stage independent_validation --workers 4

Reproduction: replace --seed/--count with --fixtures path/to/fixtures.json and
use --stage reproduction. Fixtures are always labelled non-independent.
--count counts physical layouts, not layout x error-law x rounding runs.
Source/configuration/selection locks and code snapshots precede case generation.
"""
import argparse
import copy
import hashlib
import json
import platform
import re
import shutil
import sys
import time
import traceback
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import scipy

from question3.interface import Client
from question4.audit import audit
from question4.cases import make_case
from question4.simulator import Simulator
from .analysis import analyze


PROJECT = Path(__file__).resolve().parents[2]
INNOVATION = PROJECT / 'question4' / 'innovation'
FAMILIES = ('uniform', 'outward', 'inward', 'tangent', 'cluster', 'edge')
ERROR_MODES = ('spatial_hash', 'positive', 'negative', 'smooth', 'zero')
ROUNDINGS = ('bounded', 'pre_round_stress')
FAILURE_PENALTY_S = 360000.


class PublicClient:
    """Policy capability: public actions, observations and accounting only."""
    __slots__ = ('__client',)

    def __init__(self, client):
        self.__client = client

    @property
    def position(self):
        return self.__client.position

    @property
    def channel(self):
        return self.__client.channel

    def enter(self):
        return self.__client.enter()

    def measure(self, *args, **kwargs):
        return self.__client.measure(*args, **kwargs)

    def clear(self, *args, **kwargs):
        return self.__client.clear(*args, **kwargs)

    def exit(self):
        return self.__client.exit()

    def metrics(self):
        return self.__client.metrics()


def canonical_sha256(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.writing')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def source_hashes():
    paths = set((PROJECT / 'question4').glob('*.py'))
    paths.update((PROJECT / 'question4' / 'certificates').glob('*.json'))
    paths.update(INNOVATION.glob('*.py'))
    paths.update(INNOVATION.glob('baseline*.json'))
    paths.update(INNOVATION.glob('frozen_manifest.json'))
    frozen = INNOVATION / 'frozen_baseline'
    paths.update(frozen.rglob('*.py'))
    paths.update(frozen.rglob('*.json'))
    paths.add(PROJECT / 'question3' / 'interface.py')
    return {str(path.relative_to(PROJECT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(paths)}


def _csv(value, allowed):
    result = [part.strip() for part in value.split(',') if part.strip()]
    if not result or len(result) != len(set(result)) or any(part not in allowed for part in result):
        raise argparse.ArgumentTypeError(f'Expected distinct comma-separated values from {", ".join(allowed)}')
    return result


def _layout_identity(case):
    # Source parameters, not seed or error law, define a physical layout block.
    sources = sorted(case['sources'], key=lambda source: source['channel'])
    return canonical_sha256(sources)


def _load_layouts(args):
    if args.fixtures:
        loaded = json.loads(Path(args.fixtures).read_text(encoding='utf-8'))
        if isinstance(loaded, dict):
            loaded = loaded.get('layouts', loaded.get('cases'))
        if not isinstance(loaded, list) or not loaded:
            raise ValueError('Fixtures must contain a nonempty list of case/layout objects')
        seen = set()
        layouts = []
        for case in loaded:
            identity = _layout_identity(case)
            if identity not in seen:
                case = copy.deepcopy(case)
                case['layout_sha256'] = identity
                case['layout_id'] = f'{case.get("family", "fixture")}_{identity[:16]}'
                layouts.append(case)
                seen.add(identity)
        return layouts
    return [make_case(args.seed + index, FAMILIES[index % len(FAMILIES)]) for index in range(args.count)]


def _expand_cases(layouts, error_modes, roundings):
    cases = []
    seen = set()
    for layout in layouts:
        digest = _layout_identity(layout)
        if digest in seen:
            raise ValueError('Duplicate physical layout in generated dataset')
        seen.add(digest)
        layout_id = f'{layout.get("family", "fixture")}_{digest[:16]}'
        for error_mode in error_modes:
            for rounding in roundings:
                case = copy.deepcopy(layout)
                case.update(layout_id=layout_id, layout_sha256=digest, error_mode=error_mode,
                            rounding=rounding, id=f'{layout_id}__{error_mode}__{rounding}')
                cases.append(case)
    return cases


def _run_case(task):
    case, configs, output, stage, reference = task
    from question4.innovation.strategy import run

    rows = []
    names = list(configs)
    offset = int(case['layout_sha256'][:8], 16) % len(names)
    names = names[offset:] + names[:offset]
    for name in names:
        folder = Path(output) / name / case['id']
        folder.mkdir(parents=True, exist_ok=False)
        records, events = [], []
        env = Simulator(case, rounding=case['rounding'])
        client = Client(env, 'SELF', records.append)
        started = time.perf_counter()
        exception_trace = None
        try:
            result = run(PublicClient(client), copy.deepcopy(configs[name]), events.append)
            if not isinstance(result, dict):
                raise TypeError('Strategy must return a dictionary')
        except Exception as exc:
            exception_trace = traceback.format_exc()
            result = dict(status='incomplete', failure=f'{type(exc).__name__}: {exc}', metrics=client.metrics())
        elapsed = time.perf_counter() - started
        # This is the first evaluator truth access. Neither case nor env goes to run().
        truth = env.evaluation()
        try:
            checked = audit(case, records, result)
        except Exception as exc:
            checked = dict(passed=False, failure=f'{type(exc).__name__}: {exc}', traceback=traceback.format_exc())
        try:
            from .audit import audit_regions
            checked['regions'] = audit_regions(case, events)
            checked['passed'] = bool(checked.get('passed')) and bool(checked['regions'].get('passed'))
        except Exception as exc:
            checked['regions'] = dict(passed=False, failure=f'{type(exc).__name__}: {exc}',
                                      traceback=traceback.format_exc())
            checked['passed'] = False
        status = result.get('status', 'incomplete')
        false_complete = status == 'complete' and truth['cleared'] != truth['total']
        success = status == 'complete' and truth['cleared'] == truth['total'] and bool(checked.get('passed'))
        virtual_s = max(float(truth['virtual_time_s']), float(client.metrics()['virtual_time_s']))
        row = dict(case_id=case['id'], layout_id=case['layout_id'], layout_sha256=case['layout_sha256'],
                   seed=case.get('seed'), family=case.get('family', 'fixture'),
                   error_mode=case['error_mode'], rounding=case['rounding'], stage=stage,
                   config=name, reference=reference, status=status, success=success,
                   false_complete=false_complete, cleared=truth['cleared'], total=truth['total'],
                   metrics=client.metrics(), elapsed_s=elapsed, audit=checked,
                   failure=result.get('failure'), exception_trace=exception_trace,
                   penalized_virtual_s=virtual_s if success else max(virtual_s, FAILURE_PENALTY_S),
                   event_counts=dict(Counter(event.get('event', event.get('type', 'untyped')) for event in events)))
        write_json(folder / 'result.json', dict(summary=row, strategy=result, evaluation=truth))
        write_json(folder / 'evaluator_hidden_case.json', case)
        for filename, items in (('actions.jsonl', records), ('strategy.jsonl', events)):
            with (folder / filename).open('x', encoding='utf-8') as handle:
                for item in items:
                    handle.write(json.dumps(item, ensure_ascii=False, allow_nan=False) + '\n')
        rows.append(row)
        print(f'RUN {case["id"]} {name} virtual_s={virtual_s:.3f} penalized_s={row["penalized_virtual_s"]:.3f} '
              f'complete={truth["cleared"]}/{truth["total"]} audit={bool(checked.get("passed"))} wall_s={elapsed:.3f}', flush=True)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--configs', required=True, help='JSON object mapping configuration names to dictionaries')
    parser.add_argument('--output', required=True, help='New output directory; existing outputs are refused')
    parser.add_argument('--seed', type=int, default=940000)
    parser.add_argument('--count', type=int, default=24, help='Independent physical layouts, cycling six families')
    parser.add_argument('--error-modes', default='spatial_hash,positive,negative,smooth')
    parser.add_argument('--roundings', default='bounded,pre_round_stress')
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--fixtures', help='Previously generated fixtures: reproduction, never independent validation')
    parser.add_argument('--stage', default='development')
    parser.add_argument('--lock', help='Earlier lock.json or its experiment directory; verifies immutable source/config/selection')
    parser.add_argument('--selection', help='Decision/selection JSON or text to persist and hash before generation')
    parser.add_argument('--reference', help='Defaults to BASE if present, otherwise first configuration')
    args = parser.parse_args()
    if not __debug__:
        parser.error('Python optimization disables assertions in the physical auditor; run without -O')
    if args.count < 1 or args.workers < 1:
        parser.error('--count and --workers must be positive')
    try:
        error_modes = _csv(args.error_modes, ERROR_MODES)
        roundings = _csv(args.roundings, ROUNDINGS)
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))
    output = Path(args.output).resolve()
    if output.exists():
        parser.error(f'Output already exists: {output}')
    configs = json.loads(Path(args.configs).read_text(encoding='utf-8'))
    if not isinstance(configs, dict) or not configs or any(not isinstance(value, dict) for value in configs.values()):
        parser.error('Configuration JSON must be a nonempty object mapping names to dictionaries')
    if any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name) for name in configs):
        parser.error('Configuration names must be safe directory names: letters, numbers, _, ., -')
    reference = args.reference or ('BASE' if 'BASE' in configs else next(iter(configs)))
    if reference not in configs:
        parser.error('Reference configuration is absent from --configs')
    is_validation = 'validation' in args.stage.lower() and not any(
        word in args.stage.lower() for word in ('reproduction', 'not_independent', 'not_new'))
    if is_validation and not args.lock:
        parser.error('Independent validation requires --lock from an earlier frozen selection')
    if is_validation and args.fixtures:
        parser.error('Existing fixtures are reproduction; use --stage reproduction_not_independent')
    hashes = source_hashes()
    selection_bytes = (Path(args.selection).read_bytes() if args.selection else
                       json.dumps(dict(configurations=list(configs), reference=reference,
                                       declaration='Configuration set frozen before layout generation'),
                                  sort_keys=True).encode())
    selection_hash = hashlib.sha256(selection_bytes).hexdigest()
    previous = None
    lock_path = None
    if args.lock:
        lock_path = Path(args.lock).resolve()
        if lock_path.is_dir():
            lock_path /= 'lock.json'
        previous = json.loads(lock_path.read_text(encoding='utf-8'))
        if previous['code_sha256'] != hashes:
            changed = sorted(key for key in set(previous['code_sha256']) | set(hashes)
                             if previous['code_sha256'].get(key) != hashes.get(key))
            parser.error('Source changed after lock: ' + ', '.join(changed))
        if any(previous['configs'].get(name) != config for name, config in configs.items()):
            parser.error('Configuration changed after lock')
        if args.selection and previous['selection_sha256'] != selection_hash:
            parser.error('Selection decision changed after lock')
        if not args.selection:
            selection_bytes = (lock_path.parent / 'selection_snapshot.txt').read_bytes()
            selection_hash = hashlib.sha256(selection_bytes).hexdigest()
            if selection_hash != previous['selection_sha256']:
                parser.error('Previous selection snapshot does not match its lock')
        if previous.get('reference') != reference:
            parser.error('Reference configuration changed after lock')
    lock = dict(schema_version=1, stage=args.stage, created_unix=time.time(),
                code_sha256=hashes, code_bundle_sha256=canonical_sha256(hashes),
                configs=configs, configs_sha256=canonical_sha256(configs),
                selection_sha256=selection_hash, reference=reference,
                prior_lock=str(lock_path) if lock_path else None,
                prior_lock_sha256=hashlib.sha256(lock_path.read_bytes()).hexdigest() if lock_path else None,
                generator_seed=None if args.fixtures else args.seed,
                generator_count=None if args.fixtures else args.count,
                families=list(FAMILIES), error_modes=error_modes, roundings=roundings,
                fixture_source=str(Path(args.fixtures).resolve()) if args.fixtures else None,
                statistical_unit='physical layout', failure_penalty_s=FAILURE_PENALTY_S)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'configs.json', configs)
    (output / 'selection_snapshot.txt').write_bytes(selection_bytes)
    write_json(output / 'lock.json', lock)
    for name, digest in hashes.items():
        destination = output / 'code_snapshot' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PROJECT / name, destination)
        if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
            raise RuntimeError('Source changed during snapshot: ' + name)
    write_json(output / 'snapshot_complete.json', dict(completed_unix=time.time(), code_bundle_sha256=lock['code_bundle_sha256']))
    # No case generation or fixture parsing occurs before the persisted lock/snapshot.
    layouts = _load_layouts(args)
    cases = _expand_cases(layouts, error_modes, roundings)
    identities = {case['layout_sha256'] for case in cases}
    if is_validation and lock_path:
        old_fixtures = lock_path.parent / 'fixtures.json'
        if old_fixtures.exists():
            old_cases = json.loads(old_fixtures.read_text(encoding='utf-8'))
            overlap = identities & {_layout_identity(case) for case in old_cases}
            if overlap:
                raise RuntimeError(f'Independent validation reuses {len(overlap)} layouts from its lock batch')
    write_json(output / 'fixtures.json', cases)
    provenance = dict(stage=args.stage, independent_new_layouts=not bool(args.fixtures),
                      independent_validation=bool(is_validation and not args.fixtures),
                      reuse_label='reproduction_not_independent' if args.fixtures else 'new_generated_layouts',
                      fixture_source=lock['fixture_source'], layouts=len(identities), scenarios=len(cases),
                      algorithm_runs=len(cases) * len(configs), error_modes=error_modes, roundings=roundings,
                      family_layout_counts=dict(Counter(layout.get('family', 'fixture') for layout in layouts)),
                      layout_sha256=sorted(identities), fixtures_sha256=canonical_sha256(cases),
                      generated_after_snapshot_unix=time.time(), official_runs=0, http_runs=0,
                      lock_sha256=hashlib.sha256((output / 'lock.json').read_bytes()).hexdigest())
    write_json(output / 'metadata.json', provenance)
    print(f'START stage={args.stage} layouts={len(identities)} scenarios={len(cases)} '
          f'configs={len(configs)} runs={provenance["algorithm_runs"]} workers={args.workers}', flush=True)
    rows = []
    started = time.perf_counter()
    environment = dict(python=sys.version, numpy=np.__version__, scipy=scipy.__version__, platform=platform.platform())

    def persist(completed, invalid_reason=None):
        ordered = sorted(rows, key=lambda row: (row['case_id'], list(configs).index(row['config'])))
        write_json(output / 'summary.json', dict(stage=args.stage, provenance=provenance, environment=environment,
                                                 elapsed_s=time.perf_counter() - started,
                                                 completed_scenarios=completed, expected_scenarios=len(cases),
                                                 batch_invalid_reason=invalid_reason,
                                                 rows=ordered))
        print(f'PROGRESS scenarios={completed}/{len(cases)} runs={len(rows)}/{provenance["algorithm_runs"]} '
              f'failed={sum(not row["success"] for row in rows)} elapsed_s={time.perf_counter() - started:.1f}', flush=True)

    tasks = [(case, configs, str(output), args.stage, reference) for case in cases]
    pool, pending, completed, active_case = None, {}, 0, None
    try:
        if args.workers == 1:
            for task in tasks:
                active_case = task[0]['id']
                rows.extend(_run_case(task))
                completed += 1
                persist(completed)
        else:
            pool = ProcessPoolExecutor(max_workers=args.workers)
            pending = {pool.submit(_run_case, task): task[0]['id'] for task in tasks}
            for future in as_completed(pending):
                active_case = pending[future]
                rows.extend(future.result())
                completed += 1
                persist(completed)
        active_case = None
        stable_sources = source_hashes() == hashes
        write_json(output / 'integrity.json', dict(source_unchanged_during_run=stable_sources,
                                                  finished_unix=time.time()))
        if not stable_sources:
            raise RuntimeError('Experimental source changed during execution; batch is not a locked result')
        report = analyze(rows, reference=reference)
        report['provenance'] = provenance
        write_json(output / 'comparison.json', report)
        print(json.dumps({name: {key: value[key] for key in ('complete', 'runs', 'mean_s', 'p95_s', 'max_s',
                                                           'gain_ratio_of_means_pct')}
                          for name, value in report['configurations'].items()}, indent=2), flush=True)
    except BaseException as exc:
        failure = dict(batch_valid=False, kind='framework_failure', failure=f'{type(exc).__name__}: {exc}',
                       traceback=traceback.format_exc(), active_case_id=active_case,
                       completed_scenarios=completed, expected_scenarios=len(cases),
                       retained_summary_runs=len(rows), expected_runs=provenance['algorithm_runs'],
                       failed_unix=time.time(),
                       interpretation='Batch invalid; absent runs are not fabricated policy performance observations.')
        write_json(output / 'batch_failure.json', failure)
        persist(completed, invalid_reason=failure['failure'])
        for future in pending:
            future.cancel()
        print('BATCH INVALID: ' + failure['failure'], flush=True)
        raise
    finally:
        if pool is not None:
            pool.shutdown(wait=True, cancel_futures=True)
    if any(not row['success'] for row in rows):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
