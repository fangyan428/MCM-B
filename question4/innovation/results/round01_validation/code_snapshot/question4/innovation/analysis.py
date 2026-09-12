"""Layout-blocked statistics for Q4 SELF experiments; no policy or simulator calls.

Examples (all paths are relative to the project root)::

    python -m question4.innovation.analysis --input question4/innovation/results/dev \
        --output question4/innovation/results/dev/statistics.json --bootstrap 5000

Each physical layout is one resampling block. Error laws and serialization models
on that layout stay together. Family-stratified bootstrap preserves the number of
layouts in each of the six generator families. Positive paired gain means faster.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np


def _mean_mapping(rows, section):
    keys = sorted({key for row in rows for key in row.get('metrics', {}).get(section, {})})
    return {key: float(np.mean([row.get('metrics', {}).get(section, {}).get(key, 0.)
                               for row in rows])) for key in keys}


def _summary(rows):
    values = np.asarray([row['penalized_virtual_s'] for row in rows], dtype=float)
    raw = np.asarray([row['metrics']['virtual_time_s'] for row in rows], dtype=float)
    worst = rows[int(np.argmax(values))]
    return dict(runs=len(rows), layouts=len({row['layout_id'] for row in rows}),
                complete=sum(bool(row['success']) for row in rows),
                failed=sum(not row['success'] for row in rows),
                false_complete=sum(bool(row.get('false_complete')) for row in rows),
                mean_s=float(values.mean()), p95_s=float(np.percentile(values, 95)),
                max_s=float(values.max()), raw_mean_s=float(raw.mean()),
                raw_p95_s=float(np.percentile(raw, 95)), raw_max_s=float(raw.max()),
                worst_case=worst['case_id'],
                components=_mean_mapping(rows, 'components'),
                phases=_mean_mapping(rows, 'phases'),
                counts=_mean_mapping(rows, 'counts'),
                wall_mean_s=float(np.mean([row.get('elapsed_s', 0.) for row in rows])),
                wall_p95_s=float(np.percentile([row.get('elapsed_s', 0.) for row in rows], 95)),
                failures=[dict(case_id=row['case_id'], status=row['status'],
                               failure=row.get('failure'), audit=row.get('audit'))
                          for row in rows if not row['success']])


def _paired(rows, baseline, worst_count=10):
    pairs = [(baseline[row['case_id']], row) for row in rows if row['case_id'] in baseline]
    if not pairs:
        return dict(paired_runs=0)
    ref = np.asarray([left['penalized_virtual_s'] for left, _ in pairs], dtype=float)
    val = np.asarray([right['penalized_virtual_s'] for _, right in pairs], dtype=float)
    gains = (ref - val) / ref * 100
    blocks = defaultdict(list)
    for left, right in pairs:
        blocks[right['layout_id']].append((left['penalized_virtual_s'], right['penalized_virtual_s']))
    layout_gains = [100 * (1 - np.mean([v for _, v in block]) / np.mean([r for r, _ in block]))
                    for block in blocks.values()]
    worst = sorted(zip(pairs, gains), key=lambda item: item[1])[:worst_count]
    return dict(paired_runs=len(pairs), paired_layouts=len(blocks),
                gain_ratio_of_means_pct=float((1 - val.mean() / ref.mean()) * 100),
                mean_paired_gain_pct=float(gains.mean()),
                mean_layout_gain_pct=float(np.mean(layout_gains)),
                mean_paired_saving_s=float((ref - val).mean()),
                paired_gain_p05_pct=float(np.percentile(gains, 5)),
                worst_gain_pct=float(gains.min()),
                wins=int((val < ref).sum()), ties=int((val == ref).sum()),
                losses=int((val > ref).sum()),
                worst_paired_cases=[dict(case_id=right['case_id'], layout_id=right['layout_id'],
                                         family=right['family'], error_mode=right['error_mode'],
                                         rounding=right['rounding'], baseline_s=left['penalized_virtual_s'],
                                         candidate_s=right['penalized_virtual_s'],
                                         gain_pct=float(gain),
                                         regression_s=right['penalized_virtual_s'] - left['penalized_virtual_s'])
                                    for ((left, right), gain) in worst])


def _bootstrap(rows, baseline, samples, seed):
    blocks = defaultdict(list)
    families = {}
    for row in rows:
        ref = baseline.get(row['case_id'])
        if ref is None:
            continue
        blocks[row['layout_id']].append((ref['penalized_virtual_s'], row['penalized_virtual_s']))
        families[row['layout_id']] = row['family']
    if len(blocks) < 2:
        return dict(samples=0, unavailable_reason='At least two independent layout blocks are required.')
    strata = defaultdict(list)
    for layout_id, pairs in blocks.items():
        # Use sums and run count to support explicit fixture subsets without treating
        # individual error laws or roundings as independent observations.
        pair = np.asarray(pairs, dtype=float)
        strata[families[layout_id]].append([pair[:, 0].sum(), pair[:, 1].sum(), len(pair)])
    rng = np.random.default_rng(seed)
    total = np.zeros((samples, 3), dtype=float)
    for family in sorted(strata):
        values = np.asarray(strata[family], dtype=float)
        indices = rng.integers(0, len(values), size=(samples, len(values)))
        total += values[indices].sum(axis=1)
    gain = 100 * (1 - total[:, 1] / total[:, 0])
    saving = (total[:, 0] - total[:, 1]) / total[:, 2]
    return dict(method='paired layout-block bootstrap stratified by generator family',
                samples=samples, seed=seed, layouts=len(blocks),
                family_layout_counts={key: len(value) for key, value in sorted(strata.items())},
                gain_ratio_of_means_pct_ci95=[float(x) for x in np.percentile(gain, [2.5, 97.5])],
                mean_paired_saving_s_ci95=[float(x) for x in np.percentile(saving, [2.5, 97.5])],
                bootstrap_fraction_gain_above_zero=float(np.mean(gain > 0)),
                bootstrap_fraction_gain_above_one_pct=float(np.mean(gain > 1)))


def analyze(rows, reference=None, bootstrap=0, seed=20260912, worst_count=10):
    if not rows:
        return dict(reference=reference, configurations={}, groups={}, independent_layouts=0)
    names = list(dict.fromkeys(row['config'] for row in rows))
    reference = reference or ('BASE' if 'BASE' in names else names[0])
    if reference not in names:
        raise ValueError(f'Reference configuration absent: {reference}')
    seen = set()
    for row in rows:
        key = (row['config'], row['case_id'])
        if key in seen:
            raise ValueError(f'Duplicate configuration/case observation: {key}')
        seen.add(key)
    baseline = {row['case_id']: row for row in rows if row['config'] == reference}
    configs = {}
    groups = {}
    for name in names:
        selected = [row for row in rows if row['config'] == name]
        result = _summary(selected)
        result.update(_paired(selected, baseline, worst_count))
        result['all_complete_and_audited'] = result['failed'] == 0
        if bootstrap:
            result['bootstrap'] = _bootstrap(selected, baseline, bootstrap, seed)
        configs[name] = result
    for dimension in ('family', 'error_mode', 'rounding'):
        groups[dimension] = {}
        for value in sorted({row[dimension] for row in rows}):
            subset = [row for row in rows if row[dimension] == value]
            groups[dimension][value] = {}
            for name in names:
                selected = [row for row in subset if row['config'] == name]
                if selected:
                    result = _summary(selected)
                    result.update(_paired(selected, baseline, min(3, worst_count)))
                    groups[dimension][value][name] = result
    return dict(reference=reference, independent_layouts=len({row['layout_id'] for row in rows}),
                statistical_unit='physical layout; all error laws and roundings stay in the same block',
                primary_metric='whole-game virtual seconds; unsuccessful runs use max(raw seconds, 360000)',
                configurations=configs, groups=groups)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--input', required=True, help='Experiment directory or summary.json')
    parser.add_argument('--output', required=True, help='New JSON statistics file; existing files are refused')
    parser.add_argument('--reference', help='Defaults to BASE if present, otherwise first configuration')
    parser.add_argument('--bootstrap', type=int, default=5000, choices=[0, 5000, 10000])
    parser.add_argument('--seed', type=int, default=20260912, help='Bootstrap RNG seed, not layout seed')
    parser.add_argument('--worst-count', type=int, default=10)
    args = parser.parse_args()
    source = Path(args.input)
    if source.is_dir():
        source /= 'summary.json'
    output = Path(args.output)
    if output.exists():
        parser.error(f'Output already exists: {output}')
    summary = json.loads(source.read_text(encoding='utf-8'))
    report = analyze(summary['rows'], args.reference, args.bootstrap, args.seed, args.worst_count)
    report['source_summary'] = str(source.resolve())
    report['provenance'] = summary.get('provenance', {})
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write('\n')
    print(json.dumps({name: {key: value[key] for key in ('complete', 'runs', 'mean_s', 'p95_s', 'max_s',
                                                       'gain_ratio_of_means_pct')}
                      for name, value in report['configurations'].items()}, indent=2), flush=True)


if __name__ == '__main__':
    main()
