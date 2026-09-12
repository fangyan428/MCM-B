"""Locked paired experiment runner; fixture truth is never passed to strategy."""
import argparse
import hashlib
import json
import platform
import shutil
import time
from pathlib import Path
import numpy as np
from question3.interface import Client
from .simulator import Simulator
from .strategy import run
from .cases import fixtures
from .audit import audit

def write(path,data):
    Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def source_hashes():
    paths=list(Path('question4').glob('*.py'))+[Path('question3/interface.py')]
    return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--configs',required=True)
    p.add_argument('--seed',type=int,default=41000);p.add_argument('--count',type=int,default=24)
    p.add_argument('--fixtures');p.add_argument('--lock');p.add_argument('--stage',default='development')
    p.add_argument('--rounding',default='bounded',choices=['bounded','pre_round_stress'])
    args=p.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    configs=json.loads(Path(args.configs).read_text());hashes=source_hashes()
    lock=dict(code_sha256=hashes,configs=configs,created_unix=time.time(),stage=args.stage,
              generator_seed=args.seed,generator_count=args.count,rounding=args.rounding)
    if args.lock:
        old=json.loads(Path(args.lock).read_text())
        assert old['code_sha256']==hashes,'Code changed after lock'
        assert all(old['configs'].get(k)==v for k,v in configs.items()),'Configuration changed after lock'
    write(out/'lock.json',lock)
    for name in hashes:
        dest=out/'code_snapshot'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(name,dest)
    # Generate new cases ONLY after code/config lock is persisted.
    cases=json.loads(Path(args.fixtures).read_text()) if args.fixtures else fixtures(args.seed,args.count)
    write(out/'fixtures.json',cases)
    rows=[];started=time.perf_counter()
    for case in cases:
        for name,config in configs.items():
            folder=out/name/case['id'];folder.mkdir(parents=True)
            records=[];events=[];env=Simulator(case,rounding=args.rounding)
            client=Client(env,'SELF',records.append);t=time.perf_counter()
            try:
                result=run(client,config,events.append)
                checked=audit(case,records,result)
            except Exception as exc:
                result=dict(status='incomplete',failure=f'{type(exc).__name__}: {exc}',metrics=client.metrics());checked=dict(passed=False)
            elapsed=time.perf_counter()-t;truth=env.evaluation()
            row=dict(case_id=case['id'],family=case['family'],config=name,status=result['status'],
                     cleared=truth['cleared'],total=truth['total'],metrics=client.metrics(),elapsed_s=elapsed,audit=checked,
                     failure=result.get('failure'))
            rows.append(row);write(folder/'result.json',result)
            for filename,items in [('actions.jsonl',records),('strategy.jsonl',events)]:
                (folder/filename).write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in items))
        print(case['id'],' '.join(f"{r['config']}:{r['metrics']['virtual_time_s']:.1f}/{r['status']}" for r in rows[-len(configs):]),flush=True)
        write(out/'summary.json',dict(stage=args.stage,rows=rows,platform=platform.platform(),elapsed_s=time.perf_counter()-started))
    reference=next(iter(configs));report={}
    base={r['case_id']:r for r in rows if r['config']==reference}
    for name in configs:
        selected=[r for r in rows if r['config']==name];values=np.array([r['metrics']['virtual_time_s'] for r in selected])
        ref=np.array([base[r['case_id']]['metrics']['virtual_time_s'] for r in selected]);gain=(ref-values)/ref*100
        report[name]=dict(mean_s=float(values.mean()),p95_s=float(np.percentile(values,95)),
                          gain_ratio_of_means_pct=float((1-values.mean()/ref.mean())*100),
                          mean_paired_gain_pct=float(gain.mean()),worst_gain_pct=float(gain.min()),
                          complete=sum(r['status']=='complete' and r['cleared']==r['total'] and r['audit']['passed'] for r in selected),
                          cases=len(selected),components={k:float(np.mean([r['metrics']['components'][k] for r in selected])) for k in selected[0]['metrics']['components']},
                          failures=[r['case_id'] for r in selected if r['status']!='complete'])
    write(out/'comparison.json',report);print(json.dumps(report,indent=2),flush=True)
    if any(r['status']!='complete' or not r['audit']['passed'] for r in rows):raise SystemExit(1)

if __name__=='__main__':main()
