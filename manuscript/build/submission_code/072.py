"""Paired self experiments. Hidden cases are only used by the evaluator and audit."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

import numpy as np
from question3.audit import audit_folder
from question3.interface import Client, JsonlLog
from question3.run_innovation_http import PublicClient
from question3.simulator import Simulator
from question3.innovation.strategy import run as current_run
from .strategy import run as candidate_run
from .fixtures import generate

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'question3/results/dispatch_20260913'
VARIANTS = ('CURRENT', 'COVERAGE_ORDER', 'COVERAGE_PRIORITY', 'SERVICE_PAIR', 'SERVICE_TOUR')
ROUNDINGS = ('bounded', 'pre_round_stress')


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def hashes():
    paths = []
    for directory in ('question1', 'question2', 'question3', 'question3/innovation', 'question3/dispatch_refinement'):
        paths += sorted((ROOT / directory).glob('*.py'))
    paths += [ROOT / 'question3/innovation/best_candidate.json', HERE / 'PROTOCOL.md']
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def audit_geometry(folder):
    case = json.loads((folder / 'evaluator_hidden_case.json').read_text())
    truth = {s['channel']: np.array([s['x'], s['y']]) for s in case['sources']}
    counts = {}
    for line in (folder / 'strategy.jsonl').read_text().splitlines():
        event = json.loads(line)
        kind = event['type']
        counts[kind] = counts.get(kind, 0) + 1
        if kind not in ('feasible_update', 'certified_measure', 'certified_clear'):
            continue
        vertices, source = np.asarray(event['vertices']), truth[event['channel']]
        assert len(vertices) and np.isfinite(vertices).all()
        edges = np.roll(vertices, -1, axis=0) - vertices
        delta = source - vertices
        cross = edges[:, 0] * delta[:, 1] - edges[:, 1] * delta[:, 0]
        assert np.all(cross >= -1e-4) or np.all(cross <= 1e-4), 'True source excluded'
        if kind in ('certified_measure', 'certified_clear'):
            radius = event['radius']
            assert np.linalg.norm(vertices - event['point'], axis=1).max() <= radius + 1e-8
            assert radius < (1000 if kind == 'certified_measure' else 20)
    return counts


def one_run(job):
    case, variant, config, rounding, stage = job
    folder = OUT / stage / rounding / variant / case['id']
    folder.mkdir(parents=True, exist_ok=False)
    dump(folder / 'evaluator_hidden_case.json', case)
    actions, events = JsonlLog(folder / 'actions.jsonl'), JsonlLog(folder / 'strategy.jsonl')
    env = Simulator(case, rounding=rounding)
    client = Client(env, 'SELF', actions, config['baseline_config']['real_time_reserve_s'])
    start = time.perf_counter()
    try:
        result = (current_run if variant == 'CURRENT' else candidate_run)(PublicClient(client), config, events)
    except Exception as exc:
        result = dict(status='incomplete', failure=f'{type(exc).__name__}: {exc}',
                      metrics=client.metrics(), exit_confirmed=False)
    finally:
        actions.close()
        events.close()
    elapsed = time.perf_counter() - start
    truth = env.evaluation()
    success = result['status'] == 'complete' and not truth['remaining_channels']
    row = dict(case_id=case['id'], seed=case['seed'], family=case['family'],
               source_count=truth['total'], error_mode=case['error_mode'],
               variant=variant, rounding=rounding, stage=stage,
               status=result['status'], failure=result.get('failure'),
               success=success, false_complete=result['status'] == 'complete' and not success,
               cleared=truth['cleared'], total=truth['total'],
               elapsed_wall_s=elapsed, metrics=result['metrics'])
    dump(folder / 'result.json', dict(summary=row, strategy=result))
    try:
        if success:
            row['audited_actions'] = audit_folder(folder)
            row['event_counts'] = audit_geometry(folder)
            row['audit'] = 'pass'
        else:
            row['audit'] = 'incomplete retained'
    except Exception as exc:
        row.update(success=False, false_complete=True, audit=f'{type(exc).__name__}: {exc}')
    row['penalized_virtual_s'] = truth['virtual_time_s'] if row['success'] else max(360000., truth['virtual_time_s'])
    dump(folder / 'result.json', dict(summary=row, strategy=result))
    return row


def aggregate(rows):
    result = {}
    for rounding in ROUNDINGS:
        groups = {}
        for name in sorted({r['variant'] for r in rows}):
            block = [r for r in rows if r['variant'] == name and r['rounding'] == rounding]
            if not block:
                continue
            values = [r['penalized_virtual_s'] for r in block]
            groups[name] = dict(runs=len(block), complete=sum(r['success'] for r in block),
                                failures=sum(not r['success'] for r in block),
                                false_complete=sum(r['false_complete'] for r in block),
                                mean=float(np.mean(values)), p95=float(np.percentile(values, 95)),
                                maximum=max(values),
                                mean_per_source=float(np.mean([r['penalized_virtual_s'] / r['total'] for r in block])),
                                wall_p95=float(np.percentile([r['elapsed_wall_s'] for r in block], 95)))
        if 'CURRENT' in groups:
            for value in groups.values():
                value['saving_pct'] = 100 * (1 - value['mean'] / groups['CURRENT']['mean'])
        result[rounding] = groups
    return result


def select(stats):
    eligible = []
    for name in VARIANTS[1:]:
        if all(name in stats[rounding] and stats[rounding][name]['failures'] == 0
               and stats[rounding][name]['mean'] < stats[rounding]['CURRENT']['mean']
               and stats[rounding][name]['p95'] <= stats[rounding]['CURRENT']['p95']
               and stats[rounding][name]['maximum'] <= stats[rounding]['CURRENT']['maximum']
               for rounding in ROUNDINGS):
            eligible.append((sum(stats[r][name]['mean'] / stats[r]['CURRENT']['mean'] for r in ROUNDINGS), name))
    return min(eligible)[1] if eligible else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('smoke', 'development', 'validation'), required=True)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    out = OUT / args.stage
    out.mkdir(parents=True, exist_ok=False)
    config = json.loads((ROOT / 'question3/innovation/best_candidate.json').read_text())
    configs = {name: dict(config, **({} if name == 'CURRENT' else {'dispatch_variant': name.lower()})) for name in VARIANTS}
    if args.stage == 'validation':
        lock = json.loads((OUT / 'selection_lock.json').read_text())
        assert lock['source_sha256'] == hashes(), 'Source changed after development selection'
        winner = lock['selected']
        assert winner in VARIANTS[1:]
        assert configs == lock['configs']
        names = ('CURRENT', winner)
        cases = generate(2026092300, 2, 'dispatch_validation')
    else:
        names = VARIANTS
        cases = generate(2026091300 if args.stage == 'development' else 2026091200, 1, 'dispatch_' + args.stage)
        if args.stage == 'smoke':
            cases = [c for c in cases if c['seed'] == 2026091206 and c['error_mode'] == 'spatial_hash']
    dump(out / 'fixtures.json', cases)
    dump(out / 'configs.json', {name: configs[name] for name in names})
    before = hashes()
    for file in before:
        dest = out / 'code_snapshot' / file
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / file, dest)
    dump(out / 'metadata.json', dict(stage=args.stage, generated_at=datetime.now(timezone.utc).isoformat(),
        git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        independent_layouts=len({c['seed'] for c in cases}), source_sha256=before,
        fixtures_sha256=hashlib.sha256((out / 'fixtures.json').read_bytes()).hexdigest(),
        official_runs=0, formal_runs=0))
    jobs = []
    for i, case in enumerate(cases):
        order = names[i % len(names):] + names[:i % len(names)]
        for rounding in ROUNDINGS:
            jobs.extend((case, name, configs[name], rounding, args.stage) for name in order)
    rows = []
    start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        pending = [pool.submit(one_run, job) for job in jobs]
        for future in as_completed(pending):
            row = future.result()
            rows.append(row)
            if not row['success']:
                print('FAIL', row['variant'], row['case_id'], row['failure'], row['audit'], flush=True)
            if len(rows) % 80 == 0 or len(rows) == len(jobs):
                print(f'{len(rows)}/{len(jobs)} runs; elapsed={time.perf_counter()-start:.1f}s', flush=True)
                dump(out / 'progress.json', dict(done=len(rows), total=len(jobs), failures=sum(not r['success'] for r in rows)))
    rows.sort(key=lambda r: (r['rounding'], r['case_id'], r['variant']))
    stats = aggregate(rows)
    assert hashes() == before, 'Source changed during experiment'
    dump(out / 'summary.json', dict(rows=rows, aggregates=stats))
    dump(out / 'comparison.json', stats)
    if args.stage == 'development':
        winner = select(stats)
        dump(OUT / 'selection_lock.json', dict(selected=winner, configs=configs, source_sha256=before,
             locked_at=datetime.now(timezone.utc).isoformat(), protocol='question3/dispatch_refinement/PROTOCOL.md'))
        print('Selected:', winner, flush=True)
    print(json.dumps(stats, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
