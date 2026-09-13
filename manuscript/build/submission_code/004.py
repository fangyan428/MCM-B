"""Read-only verification of existing Q4 evidence; never runs a strategy/API.

Run from project root: python manuscript/analysis/q4_verify.py
Outputs derived tables with original input SHA256 hashes.
"""
from pathlib import Path
import collections
import csv
import hashlib
import json
import math
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
RESET = ROOT / 'paper_evidence/q4_mechanism_reset_20260912'
inputs = {}


def read(path):
    path = Path(path)
    raw = path.read_bytes()
    inputs[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
    return json.loads(raw)


def summarize(rows):
    times = np.array([r['metrics']['virtual_time_s'] for r in rows])
    counts = np.array([r['cleared'] for r in rows])
    return {
        'runs': len(rows),
        'complete': sum(r['status'] == 'complete' and r['cleared'] == r['total'] and r['audit']['passed'] for r in rows),
        'mean_s': float(times.mean()),
        'p95_s': float(np.quantile(times, .95)),
        'max_s': float(times.max()),
        'mean_of_per_game_time_per_cleared_source_s': float(np.mean(times / counts)),
        'pooled_time_per_source_s': float(times.sum() / counts.sum()),
        'mean_clearance_ratio': float(np.mean(counts / np.array([r['total'] for r in rows]))),
        'mean_source_count': float(counts.mean()),
    }


latest = read(RESET / 'final_validation/summary.json')
published = read(RESET / 'FINAL_STATISTICS.json')['configurations']
latest_rows = latest['rows']
assert len(latest_rows) == 4800
assert len({(r['config'], r['case_id']) for r in latest_rows}) == 4800
assert len({r['layout_sha256'] for r in latest_rows}) == 120
stats = {}
stop_counts = {}
for name in sorted(published):
    rows = [r for r in latest_rows if r['config'] == name]
    assert len(rows) == 960
    assert all(not r['timeout'] and not r['false_complete'] and r['success'] for r in rows)
    stops = collections.Counter()
    for row in rows:
        stored = read(RESET / 'final_validation' / name / row['case_id'] / 'result.json')
        assert stored['summary'] == row
        assert stored['strategy']['metrics'] == row['metrics']
        assert len(stored['strategy']['cleared']) == row['cleared']
        assert row['penalized_virtual_s'] == row['metrics']['virtual_time_s']
        stops[row['audit']['additional']['stop']['kind']] += 1
    stats[name] = summarize(rows)
    for key in ('mean_s', 'p95_s', 'max_s'):
        assert abs(stats[name][key] - published[name][key]) < 1e-8
    stop_counts[name] = dict(stops)

historical = {}
review = read(ROOT / 'question4/results/round9_review.json')
historical_rows = []
for batch in ('round9_main', 'round9_rounding'):
    summary = read(ROOT / 'question4/results' / batch / 'summary.json')
    historical[batch] = {}
    for name in ('BASE', 'FINAL', 'COMPACT22', 'NO_CENTROID', 'NO_INFO'):
        rows = [r for r in summary['rows'] if r['config'] == name]
        assert len(rows) == 96
        for row in rows:
            raw = read(ROOT / 'question4/results' / batch / name / row['case_id'] / 'result.json')
            assert raw['metrics'] == row['metrics']
        historical[batch][name] = summarize(rows)
        for key in ('mean_s', 'p95_s'):
            assert abs(historical[batch][name][key] - review[batch]['vs_baseline'][name][key]) < 1e-8
        historical_rows.extend(dict(batch=batch, **r) for r in rows)

# Explicit geometric construction, independent of the legacy certificate auditor.
inner = 950.0
outer = 1870.0
edges = {
    'origin_inner': inner,
    'inner_inner': 2 * inner * math.sin(math.pi / 12),
    'outer_outer': 2 * outer * math.sin(math.pi / 12),
    'adjacent_inner_outer': math.sqrt(inner**2 + outer**2 - 2 * inner * outer * math.cos(math.pi / 12)),
}
assert max(edges.values()) < 1000
apothem = outer * math.cos(math.pi / 12)
assert apothem > 1800

fields = ['batch', 'config', 'case_id', 'layout_id', 'family', 'error_mode', 'rounding',
          'virtual_time_s', 'cleared', 'total', 'time_per_source_s']
with (OUT / 'q4_source_data.csv').open('w', newline='', encoding='utf-8') as stream:
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for row in historical_rows + [dict(batch='reset_final_validation', **r) for r in latest_rows]:
        record = {k: row.get(k, '') for k in fields}
        record['virtual_time_s'] = row['metrics']['virtual_time_s']
        record['time_per_source_s'] = row['metrics']['virtual_time_s'] / row['cleared']
        writer.writerow(record)

result = {
    'scope': 'Existing result JSON and summary consistency; no official or self-built strategy runs.',
    'latest': stats,
    'historical': historical,
    'latest_stop_counts': stop_counts,
    'geometry_25_stations': {'edge_lengths_m': edges, 'outer_apothem_m': apothem,
                            'triangle_count_explicit_construction': 36},
    'per_source_aggregation': 'Mean of each game virtual_time_s/cleared; pooled ratio separately labelled.',
    'inputs_verified': len(inputs),
    'input_sha256': inputs,
}
(OUT / 'q4_verification.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({k: result[k] for k in ('latest', 'historical', 'latest_stop_counts', 'geometry_25_stations', 'inputs_verified')}, ensure_ascii=False, indent=2))
