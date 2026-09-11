"""Run development-only SELF fixtures. Hidden truth is saved for evaluator replay,
never passed to strategy. Holdout comparison is deferred until user approves innovation.
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


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='question3/results/baseline_dev')
    parser.add_argument('--limit',type=int);parser.add_argument('--rounding',choices=['bounded','pre_round_stress'],default='bounded')
    args=parser.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    config=json.loads(Path('question3/configs/baseline.json').read_text());rows=[]
    (out/'config.json').write_text(json.dumps(config,indent=2))
    manifest={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path('question3').glob('*.py'))}
    manifest.update({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path('question1/solve.py'),Path('question2/strategy.py')]})
    for index,case in enumerate(development_cases()):
        if args.limit is not None and index>=args.limit:break
        folder=out/case['id'];folder.mkdir(exist_ok=True)
        (folder/'evaluator_hidden_case.json').write_text(json.dumps(case,indent=2))
        log=JsonlLog(folder/'actions.jsonl');events=JsonlLog(folder/'strategy.jsonl')
        env=Simulator(case,rounding=args.rounding)
        client=Client(env,'SELF',log,reserve_s=config['real_time_reserve_s'])
        started=time.perf_counter()
        try:result=run(client,config,events)
        except Exception as exc:result=dict(status='incomplete',failure=f'{type(exc).__name__}: {exc}',metrics=client.metrics())
        elapsed=time.perf_counter()-started
        truth=env.evaluation() # Evaluation only, after strategy turn.
        row=dict(case_id=case['id'],kind='SELF_DEVELOPMENT',rounding=args.rounding,
                 status=result['status'],failure=result.get('failure'),elapsed_wall_s=elapsed,
                 total=truth['total'],cleared=truth['cleared'],remaining_channels=truth['remaining_channels'],
                 clearance_ratio=truth['cleared']/truth['total'],
                 average_virtual_per_cleared=truth['virtual_time_s']/truth['cleared'] if truth['cleared'] else None,
                 metrics=result['metrics'])
        if result['status']=='complete' and truth['remaining_channels']:raise AssertionError('False completion!')
        for k,v in truth['components'].items():
            if abs(v-result['metrics']['components'][k])>1e-6:raise AssertionError('Accounting mismatch '+k)
        (folder/'result.json').write_text(json.dumps(dict(summary=row,strategy=result),ensure_ascii=False,indent=2))
        rows.append(row);log.close();events.close()
        print(case['id'],row['status'],f'{truth["cleared"]}/{truth["total"]}',f'{truth["virtual_time_s"]:.2f}s',flush=True)
    summary=dict(kind='SELF_DEVELOPMENT_ONLY',python=sys.version,platform=platform.platform(),config=config,
                 code_sha256=manifest,cases=rows,official_rehearsals_run=0,formal_tests_run=0,
                 note='No innovation comparisons or held-out cases run; awaiting human review.')
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    if any(row['status']!='complete' or row['clearance_ratio']!=1 for row in rows):raise SystemExit(1)

if __name__=='__main__':main()
