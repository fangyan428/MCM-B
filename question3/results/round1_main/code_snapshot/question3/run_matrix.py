"""First-round fixed factorial experiment. Saves EVERY run including failures.
Case truth accessible to evaluator only, after strategy. No holdout generation.
"""
import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path
from .cases import development_cases
from .simulator import Simulator
from .interface import Client,JsonlLog
from .strategy import run
from .modules import design_catalog
from .audit import audit_folder

VARIANTS=['baseline','A','B','C','AB','AC','BC','ABC']

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    parser.add_argument('--rounding',choices=['bounded','pre_round_stress'],default='bounded')
    parser.add_argument('--limit',type=int)
    args=parser.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    configs={n:json.loads(Path(f'question3/configs/round1/{n}.json').read_text()) for n in VARIANTS}
    fixtures=list(development_cases());rows=[]
    startup=time.perf_counter();design_catalog();catalog_startup=time.perf_counter()-startup
    files=list(Path('question3').glob('*.py'))+[Path('question1/solve.py'),Path('question2/strategy.py')]
    manifest={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    snapshot=out/'code_snapshot';snapshot.mkdir()
    for p in files:
        dest=snapshot/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(p.read_bytes())
    fixtures_hash={c['id']:hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest() for c in fixtures}
    (out/'configs.json').write_text(json.dumps(configs,indent=2))
    for i,case in enumerate(fixtures):
        if args.limit is not None and i>=args.limit:break
        # Rotate config order: no module consistently absorbs first-run overhead.
        order=VARIANTS[i%8:]+VARIANTS[:i%8]
        for name in order:
            cfg=configs[name];folder=out/name/case['id'];folder.mkdir(parents=True)
            (folder/'evaluator_hidden_case.json').write_text(json.dumps(case,indent=2),encoding='utf-8')
            log=JsonlLog(folder/'actions.jsonl');events=JsonlLog(folder/'strategy.jsonl')
            env=Simulator(case,rounding=args.rounding);client=Client(env,'SELF',log,cfg['real_time_reserve_s'])
            start=time.perf_counter()
            try:result=run(client,cfg,events)
            except Exception as exc:result=dict(status='incomplete',failure=f'{type(exc).__name__}: {exc}',metrics=client.metrics(),regions=[])
            wall=time.perf_counter()-start;truth=env.evaluation()
            row=dict(variant=name,case_id=case['id'],kind='SELF_ROUND1_DEVELOPMENT',rounding=args.rounding,
                     status=result['status'],failure=result.get('failure'),elapsed_wall_s=wall,
                     total=truth['total'],cleared=truth['cleared'],remaining_channels=truth['remaining_channels'],
                     clearance_ratio=truth['cleared']/truth['total'],
                     average_virtual_per_cleared=truth['virtual_time_s']/truth['cleared'] if truth['cleared'] else None,
                     metrics=result['metrics'])
            row['false_complete']=result['status']=='complete' and bool(truth['remaining_channels'])
            row['timeout']=bool(result.get('failure') and any(s in result['failure'].lower() for s in ('deadline','timeout','budget')))
            row['penalized_virtual_s']=truth['virtual_time_s'] if result['status']=='complete' and not truth['remaining_channels'] else max(360000,truth['virtual_time_s'])
            (folder/'result.json').write_text(json.dumps(dict(summary=row,strategy=result),ensure_ascii=False,indent=2),encoding='utf-8')
            log.close();events.close()
            if row['status']=='complete':
                try:row['audited_actions']=audit_folder(folder);row['audit']='pass'
                except Exception as exc:row['audit']='FAIL: '+str(exc);row['false_complete']=True
            else:row['audit']='incomplete run retained; no complete certificate asserted'
            rows.append(row)
            if row['status']!='complete' or row['false_complete']:print('FAIL',name,case['id'],row['failure'],row['audit'],flush=True)
        print(f'{i+1}/{len(fixtures)} {case["id"]}: '+', '.join(f'{r["variant"]}={r["metrics"]["virtual_time_s"]:.0f}' for r in rows[-8:]),flush=True)
        summary=dict(kind='SELF_ROUND1_DEVELOPMENT_NOT_HOLDOUT',rounding=args.rounding,cases=rows,
                     configs=configs,case_sha256=fixtures_hash,code_sha256=manifest,
                     catalog_startup_wall_s=catalog_startup,platform=platform.platform(),python=sys.version,
                     official_rehearsals_run=0,formal_tests_run=0,unseen_validation_cases_run=0)
        (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    if any(r['false_complete'] for r in rows):raise SystemExit(2)

if __name__=='__main__':main()
