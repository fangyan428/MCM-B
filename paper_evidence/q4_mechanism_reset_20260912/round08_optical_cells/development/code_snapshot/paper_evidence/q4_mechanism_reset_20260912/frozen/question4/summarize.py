"""Paper-ready paired statistics. Independent layouts, not duplicate noise replays, are units."""
import argparse
import json
from pathlib import Path
import numpy as np

def pair_stats(rows,candidate,reference):
    ref={r['case_id']:r for r in rows if r['config']==reference}
    chosen=[r for r in rows if r['config']==candidate]
    x=np.array([ref[r['case_id']]['metrics']['virtual_time_s'] for r in chosen])
    y=np.array([r['metrics']['virtual_time_s'] for r in chosen])
    gains=100*(1-y/x);rng=np.random.default_rng(20260912)
    ids=rng.integers(0,len(x),size=(10000,len(x)))
    boot=100*(1-y[ids].mean(axis=1)/x[ids].mean(axis=1))
    ordered=sorted(zip(gains,chosen),key=lambda t:t[0])
    return dict(n=len(x),mean_s=float(y.mean()),reference_mean_s=float(x.mean()),
        gain_pct=float(100*(1-y.mean()/x.mean())),bootstrap95_pct=np.percentile(boot,[2.5,97.5]).tolist(),
        p95_s=float(np.percentile(y,95)),reference_p95_s=float(np.percentile(x,95)),
        median_paired_gain_pct=float(np.median(gains)),wins=int(np.sum(gains>1e-7)),ties=int(np.sum(abs(gains)<=1e-7)),
        worst=[dict(case_id=r['case_id'],gain_pct=float(g),candidate_s=r['metrics']['virtual_time_s'],
            reference_s=ref[r['case_id']]['metrics']['virtual_time_s'],components=r['metrics']['components']) for g,r in ordered[:5]],
        by_family={f:dict(n=sum(r['family']==f for r in chosen),
            gain_pct=float(100*(1-np.mean([r['metrics']['virtual_time_s'] for r in chosen if r['family']==f])/
                                    np.mean([ref[r['case_id']]['metrics']['virtual_time_s'] for r in chosen if r['family']==f]))))
            for f in sorted({r['family'] for r in chosen})},
        components={k:float(np.mean([r['metrics']['components'][k] for r in chosen])) for k in chosen[0]['metrics']['components']},
        complete=sum(r['status']=='complete' and r['audit']['passed'] and r['cleared']==r['total'] for r in chosen),
        max_wall_s=max(r['elapsed_s'] for r in chosen))

def main():
    p=argparse.ArgumentParser();p.add_argument('runs',nargs='+');p.add_argument('--candidate',default='FINAL');p.add_argument('--output',required=True)
    args=p.parse_args();report={}
    for directory in args.runs:
        data=json.loads((Path(directory)/'summary.json').read_text());rows=data['rows'];names=list(dict.fromkeys(r['config'] for r in rows))
        report[Path(directory).name]=dict(total_runs=len(rows),all_complete=all(r['status']=='complete' and r['audit']['passed'] and r['cleared']==r['total'] for r in rows),
            vs_baseline={name:pair_stats(rows,name,names[0]) for name in names},
            vs_final={name:pair_stats(rows,name,args.candidate) for name in names})
    Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2))
    for batch,data in report.items():
        print(batch)
        for name,s in data['vs_final'].items():
            print(name,round(s['mean_s'],2),round(s['gain_pct'],3),[round(x,3) for x in s['bootstrap95_pct']])

if __name__=='__main__':main()
