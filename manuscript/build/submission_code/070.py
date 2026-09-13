"""Describe every paired result and apply the predeclared replacement criteria."""
import argparse
import csv
import json
from collections import defaultdict
import numpy as np
from .experiment import OUT, ROUNDINGS, aggregate, dump


def paired_summary(rows, name, rounding):
    block = [r for r in rows if r['rounding'] == rounding]
    current = {r['case_id']: r for r in block if r['variant'] == 'CURRENT'}
    pairs = []
    for row in block:
        if row['variant'] != name:
            continue
        base = current[row['case_id']]
        a, b = base['penalized_virtual_s'], row['penalized_virtual_s']
        pairs.append(dict(case_id=row['case_id'], seed=row['seed'], family=row['family'],
            source_count=row['source_count'], error_mode=row['error_mode'], rounding=rounding,
            variant=name, current_s=a, candidate_s=b, change_s=b-a, change_pct=100*(b/a-1),
            current_success=base['success'], candidate_success=row['success']))
    by_layout = defaultdict(list)
    for p in pairs:
        by_layout[p['seed']].append((p['current_s'], p['candidate_s']))
    means = np.array([np.mean(values, axis=0) for _, values in sorted(by_layout.items())])
    rng = np.random.default_rng(20260913)
    indices = rng.integers(len(means), size=(4000, len(means)))
    draws = means[indices].mean(axis=1)
    savings = 100 * (1 - draws[:, 1] / draws[:, 0])
    return dict(faster=sum(p['change_s'] < -1e-6 for p in pairs),
                slower=sum(p['change_s'] > 1e-6 for p in pairs),
                worst_relative=max(pairs, key=lambda p: p['change_pct']),
                saving_ci95_pct=np.percentile(savings, [2.5, 97.5]).tolist(),
                independent_layouts=len(means)), pairs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('development', 'validation'), required=True)
    args = parser.parse_args()
    folder = OUT / args.stage
    data = json.loads((folder / 'summary.json').read_text())
    rows, stats = data['rows'], data['aggregates']
    selected = json.loads((OUT / 'selection_lock.json').read_text())['selected']
    report = dict(stage=args.stage, selected=selected, aggregates=stats, paired={}, breakdown={},
                  audited_actions=sum(r.get('audited_actions', 0) for r in rows),
                  failures=sum(not r['success'] for r in rows), official_runs=0, formal_runs=0)
    pairs = []
    for name in sorted({r['variant'] for r in rows} - {'CURRENT'}):
        report['paired'][name] = {}
        for rounding in ROUNDINGS:
            summary, part = paired_summary(rows, name, rounding)
            report['paired'][name][rounding] = summary
            pairs.extend(part)
    for key in ('family', 'source_count', 'error_mode'):
        report['breakdown'][key] = {str(value): aggregate([r for r in rows if r[key] == value])
                                    for value in sorted({r[key] for r in rows})}
    report['replacement_passed'] = args.stage == 'validation' and selected is not None and all(
        stats[r][selected]['failures'] == 0 and stats[r]['CURRENT']['failures'] == 0
        and stats[r][selected]['saving_pct'] >= 5
        and stats[r][selected]['p95'] <= stats[r]['CURRENT']['p95']
        and stats[r][selected]['maximum'] <= stats[r]['CURRENT']['maximum']
        and stats[r][selected]['mean_per_source'] < stats[r]['CURRENT']['mean_per_source']
        for r in ROUNDINGS)
    dump(folder / 'analysis.json', report)
    with (folder / 'paired.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(pairs[0]))
        writer.writeheader()
        writer.writerows(pairs)
    print(json.dumps(dict(stage=args.stage, selected=selected,
        replacement_passed=report['replacement_passed'], failures=report['failures'],
        audited_actions=report['audited_actions'], aggregates=stats), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
