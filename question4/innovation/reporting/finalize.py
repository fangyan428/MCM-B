"""Post-run evidence, layout-block statistics and publication figures.

Run from the project root after the final locked experiment completes.
This reporting program is never imported by the policy or experiment runner.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from question4.innovation.analysis import analyze, validate_batch


ROOT = Path('question4/innovation')


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def load_batch(name):
    path = ROOT/'results'/name
    summary = json.loads((path/'summary.json').read_text())
    validate_batch(path/'summary.json', summary)
    return path, summary


def build(candidate):
    names = ['round01_dev', 'round01_validation', 'round02_dev', 'round02_validation', 'final_validation']
    batches = {name: load_batch(name) for name in names}
    final_path, summary = batches['final_validation']
    rows = summary['rows']
    stats = analyze(rows, bootstrap=10000)
    by_rounding = {rounding: analyze([r for r in rows if r['rounding'] == rounding], bootstrap=10000)
                   for rounding in ['bounded', 'pre_round_stress']}
    write(ROOT/'FINAL_STATISTICS.json', stats)
    write(ROOT/'FINAL_BY_ROUNDING.json', by_rounding)
    index = {}
    layout_sets = {}
    for name, (path, batch) in batches.items():
        rr = batch['rows']
        layout_sets[name] = {r['layout_sha256'] for r in rr}
        index[name] = dict(stage=batch['stage'], independent_layouts=len(layout_sets[name]),
                           algorithm_runs=len(rr), complete=sum(r['success'] for r in rr),
                           accepted_actions=sum(r['audit'].get('accepted_actions', 0) for r in rr),
                           elapsed_s=batch['elapsed_s'],
                           lock_sha256=hashlib.sha256((path/'lock.json').read_bytes()).hexdigest())
    overlap = {f'{a} vs {b}': len(layout_sets[a] & layout_sets[b])
               for i, a in enumerate(names) for b in names[i+1:]}
    # Historical fixtures predate this innovation directory and are evaluator owned.
    from question4.innovation.experiment import _layout_identity
    historical = set()
    for path in Path('question4/results').glob('*/fixtures.json'):
        historical.update(_layout_identity(case) for case in json.loads(path.read_text()))
    history_overlap = {name: len(layouts & historical) for name, layouts in layout_sets.items()}
    frozen = json.loads((ROOT/'frozen_manifest.json').read_text())['sha256']
    changed = [name for name, digest in frozen.items()
               if not Path(name).is_file() or hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest]
    assert not changed, changed
    for name in ('round01_validation', 'round02_validation', 'final_validation'):
        assert not history_overlap[name]
    assert not (layout_sets['final_validation'] & set.union(*(layout_sets[n] for n in names[:-1])))
    evidence = dict(candidate=candidate, batches=index, total_algorithm_runs=sum(v['algorithm_runs'] for v in index.values()),
                    total_accepted_actions=sum(v['accepted_actions'] for v in index.values()),
                    distinct_layouts=len(set.union(*layout_sets.values())), layout_overlap=overlap,
                    historical_layout_overlap=history_overlap, frozen_files_verified=len(frozen), frozen_files_changed=changed,
                    official_runs=0, cloud_pushes=0,
                    final_candidate={r: value['configurations'][candidate] for r, value in by_rounding.items()},
                    final_baseline={r: value['configurations']['BASE'] for r, value in by_rounding.items()},
                    inference='Preselected final candidate; remaining arms are descriptive ablations without multiplicity correction.')
    write(ROOT/'FINAL_EVIDENCE.json', evidence)
    configs = list(json.loads((final_path/'configs.json').read_text()))
    keyed = {(r['case_id'], r['config']): r for r in rows}
    with (ROOT/'final_paired.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['layout_id', 'seed', 'family', 'error_mode', 'rounding', 'case_id']+configs)
        for case_id in sorted({r['case_id'] for r in rows}):
            row = keyed[(case_id, 'BASE')]
            writer.writerow([row[k] for k in ['layout_id', 'seed', 'family', 'error_mode', 'rounding', 'case_id']]+
                            [keyed[(case_id, config)]['penalized_virtual_s'] for config in configs])
    # Strict single-factor comparisons of the R2 additions against their parent.
    r2 = batches['round02_validation'][1]['rows']
    comparisons = [('ADAPT_ENTRY', 'ADAPT_GATED'), ('ADAPT_SHADOW', 'ADAPT_GATED'),
                   ('ADAPT_ENTRY_SHADOW', 'ADAPT_GATED'), ('ADAPT_VALUE_GATE', 'ADAPT_GATED'),
                   ('PAIR_ENTRY', 'PAIR_GATED'), ('CENTER_BLIND', 'CENTER')]
    marginal = {f'{child} / {parent}': analyze(r2, reference=parent, bootstrap=10000)['configurations'][child]
                for child, parent in comparisons}
    write(ROOT/'STOPPING_EVIDENCE.json', marginal)
    examples = [dict(label='final_worst_relative', batch='final_validation', config=candidate,
                     **stats['configurations'][candidate]['worst_paired_cases'][0]),
                dict(label='final_absolute_slowest', batch='final_validation', config=candidate,
                     case_id=stats['configurations'][candidate]['worst_case'])]
    for child, parent in [('ADAPT_ENTRY', 'ADAPT_GATED'), ('CENTER_BLIND', 'CENTER')]:
        info = marginal[f'{child} / {parent}']['worst_paired_cases'][0]
        examples.append(dict(label='mechanism_negative', batch='round02_validation', config=child, parent=parent, **info))
    write(ROOT/'REPRESENTATIVE_CASES.json', examples)
    figures = ROOT/'figures'; figures.mkdir(exist_ok=True)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.spines.top': False,
                         'axes.spines.right': False, 'figure.dpi': 150, 'svg.fonttype': 'none'})
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2), layout='constrained')
    bounded = by_rounding['bounded']['configurations']
    order = sorted(configs, key=lambda name: bounded[name]['mean_s'])
    colors = ['#167d9a' if name == candidate else '#35465d' if name == 'BASE' else '#a9b7c5' for name in order]
    axes[0].barh(order, [bounded[n]['mean_s'] for n in order], color=colors)
    axes[0].set_xlabel('Mean whole-game virtual time (s)'); axes[0].invert_yaxis()
    axes[0].set_title('Locked final validation · bounded')
    for i, name in enumerate(order):
        axes[0].text(bounded[name]['mean_s']+20, i, f"{bounded[name]['mean_s']:.0f}", va='center', fontsize=8)
    axes[0].set_xlim(0, max(bounded[n]['mean_s'] for n in order)*1.14)
    components = [('movement_s', '#35465d'), ('detection_s', '#167d9a'), ('switch_s', '#7cafbd'),
                  ('optical_s', '#d79057'), ('laser_s', '#ddb794')]
    bottom = np.zeros(2)
    for key, color in components:
        values = np.array([bounded[n]['components'][key] for n in ['BASE', candidate]])
        axes[1].bar(['BASE', candidate], values, bottom=bottom, label=key.removesuffix('_s'), color=color)
        bottom += values
    axes[1].set_title('All actions fully charged'); axes[1].set_ylabel('Mean virtual seconds')
    axes[1].tick_params(axis='x', labelsize=8); axes[1].legend(fontsize=8)
    for i, rounding in enumerate(by_rounding):
        info = by_rounding[rounding]['configurations'][candidate]
        gain = info['gain_ratio_of_means_pct']; low, high = info['bootstrap']['gain_ratio_of_means_pct_ci95']
        axes[2].errorbar(gain, i, xerr=[[gain-low], [high-gain]], fmt='o', color='#167d9a', capsize=4)
    axes[2].axvline(0, color='#999999', lw=1); axes[2].axvline(1, color='#d79057', lw=1, ls='--')
    axes[2].set_yticks([0, 1], ['bounded', 'round stress']); axes[2].set_xlabel('Saving vs BASE (%)')
    axes[2].set_title('120 layout blocks · 95% bootstrap CI')
    for suffix in ('png', 'svg'):
        fig.savefig(figures/f'final_overview.{suffix}')
    plt.close(fig)
    worst = examples[0]['case_id']
    case = json.loads((final_path/candidate/worst/'evaluator_hidden_case.json').read_text())
    fig, axes = plt.subplots(1, 2, figsize=(10, 5), layout='constrained')
    for ax, config in zip(axes, ['BASE', candidate]):
        requests = [json.loads(line) for line in (final_path/config/worst/'actions.jsonl').read_text().splitlines()]
        points = [(0., 0.)]+[(r['payload']['position']['x'], r['payload']['position']['y']) for r in requests
                            if r['type'] == 'request' and r['path'] in ('/measure', '/clear') and r.get('attempt', 0) == 0]
        xy = np.array(points); ax.plot(xy[:, 0], xy[:, 1], color='#167d9a', lw=.8, alpha=.7)
        for source in case['sources']:
            ax.scatter(source['x'], source['y'], s=25, marker='^' if source['direction_deg'] is not None else 'o', color='#be6326')
        ax.add_patch(plt.Circle((0, 0), 1800, fill=False, color='#aaaaaa', ls='--'))
        ax.scatter(0, 0, marker='*', s=90, color='#35465d'); ax.set_aspect('equal')
        ax.set_title(f"{config}: {keyed[(worst, config)]['penalized_virtual_s']:.1f} s")
        ax.set_xlabel('x (m)'); ax.set_ylabel('y (m)')
    fig.suptitle('Worst paired regression · evaluator truth overlaid after execution', fontsize=11)
    for suffix in ('png', 'svg'):
        fig.savefig(figures/f'worst_paths.{suffix}')
    plt.close(fig)
    print(json.dumps({'candidate': candidate, 'runs': evidence['total_algorithm_runs'],
                      'layouts': evidence['distinct_layouts'], 'frozen_files_verified': len(frozen)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', required=True)
    build(parser.parse_args().candidate)
