"""Report every case, failure penalty, tails and factorial conditional effects."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from .run_matrix import VARIANTS


def good(row):return row['status']=='complete' and row['clearance_ratio']==1 and row.get('audit')=='pass' and not row.get('false_complete')
def objective(row):return row['metrics']['virtual_time_s'] if good(row) else max(360000,row['metrics']['virtual_time_s'])

def main():
    p=argparse.ArgumentParser();p.add_argument('folder');args=p.parse_args();root=Path(args.folder)
    data=json.loads((root/'summary.json').read_text());lookup={(r['variant'],r['case_id']):r for r in data['cases']}
    ids=sorted({r['case_id'] for r in data['cases']});stats=[]
    for name in VARIANTS:
        rows=[lookup[name,i] for i in ids];base=[lookup['baseline',i] for i in ids]
        values=np.array([objective(r) for r in rows]);raw=np.array([r['metrics']['virtual_time_s'] for r in rows])
        improvement=1-values/np.array([objective(r) for r in base]);wall=[r['elapsed_wall_s'] for r in rows]
        worst=int(np.argmax(values));regress=int(np.argmin(improvement));per_clear=[r['average_virtual_per_cleared'] for r in rows]
        stats.append(dict(variant=name,runs=len(rows),complete=sum(good(r) for r in rows),
                          failed=sum(not good(r) for r in rows),timeouts=sum(r['timeout'] for r in rows),
                          false_complete=sum(r['false_complete'] for r in rows),
                          mean_clearance_ratio=float(np.mean([r['clearance_ratio'] for r in rows])),
                          mean_virtual_s=float(values.mean()),raw_all_case_mean_virtual_s=float(raw.mean()),
                          p95_virtual_s=float(np.percentile(values,95)),cvar_worst10_s=float(np.sort(values)[-max(1,int(np.ceil(.1*len(rows)))):].mean()),
                          max_virtual_s=float(values.max()),max_virtual_case=ids[worst],
                          mean_case_average_per_clear_s=None if any(x is None for x in per_clear) else float(np.mean(per_clear)),
                          pooled_virtual_per_clear_s=float(raw.sum()/sum(r['cleared'] for r in rows)) if sum(r['cleared'] for r in rows) else None,
                          median_paired_improvement=float(np.median(improvement)),
                          worst_case_improvement=float(improvement.min()),worst_regression_case=ids[regress],
                          worse_than_baseline=int(np.sum(improvement < -1e-9)),wins=int(np.sum(improvement>1e-9)),
                          wall_p95_s=float(np.percentile(wall,95)),wall_max_s=max(wall),
                          mean_failed_clears=float(np.mean([r['metrics']['counts']['clear_failure'] for r in rows])),
                          max_failed_clears=max(r['metrics']['counts']['clear_failure'] for r in rows),
                          mean_components={k:float(np.mean([r['metrics']['components'][k] for r in rows])) for k in rows[0]['metrics']['components']}))
    effects=[]
    for module in 'ABC':
        for without in VARIANTS:
            if module in without or without=='baseline' and False:continue
            letters='' if without=='baseline' else without
            with_name=''.join(sorted(letters+module))
            if with_name not in VARIANTS:continue
            before=np.array([objective(lookup[without,i]) for i in ids]);after=np.array([objective(lookup[with_name,i]) for i in ids])
            change=1-after/before;k=int(np.argmin(change))
            effects.append(dict(module=module,without=without,with_variant=with_name,mean_saved_s=float(np.mean(before-after)),
                                median_paired_improvement=float(np.median(change)),wins=int(np.sum(change>1e-9)),
                                losses=int(np.sum(change< -1e-9)),worst_change=float(change[k]),worst_case=ids[k]))
    interactions=[]
    mean={s['variant']:s['mean_virtual_s'] for s in stats}
    for a,b in [('A','B'),('A','C'),('B','C')]:
        interactions.append(dict(pair=a+b,additive_interaction_s=mean[a+b]-mean[a]-mean[b]+mean['baseline'],
                                 definition='T_AB - T_A - T_B + T_baseline; negative = savings exceed additive single-module savings'))
    failures=[r for r in data['cases'] if not good(r)]
    report=dict(kind=data['kind'],rounding=data['rounding'],stats=stats,effects=effects,interactions=interactions,failures=failures,
                notes=['All runs retained. Failure/timeout/noncertified runs ranked with >=360000s penalty.',
                       'Percentiles include all cases. Fixtures are development cases, NOT held-out validation.'])
    (root/'comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    with (root/'paired_cases.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.writer(f);writer.writerow(['case_id']+VARIANTS)
        for i in ids:writer.writerow([i]+[objective(lookup[n,i]) for n in VARIANTS])
    for s in stats:print(s['variant'],f'{s["complete"]}/{s["runs"]}',f'mean={s["mean_virtual_s"]:.2f}',f'p95={s["p95_virtual_s"]:.2f}',
                         f'max={s["max_virtual_s"]:.2f}',f'median_gain={s["median_paired_improvement"]:.2%}',
                         f'worst_gain={s["worst_case_improvement"]:.2%}',s['worst_regression_case'])
    print('EFFECTS',json.dumps(effects));print('INTERACTIONS',json.dumps(interactions))

if __name__=='__main__':main()
