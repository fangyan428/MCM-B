"""Evaluator-only self experiments. Strategy inputs exclude cases and evaluator state."""
import argparse
import hashlib
import json
import math
import shutil
import statistics
import sys
import time
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'frozen'))
from question3.cases import development_cases
from question3.simulator import Simulator
from question3.interface import Client,JsonlLog
from question3.strategy import run as baseline_run
from question3.audit import audit_folder
from .strategy import run as candidate_run

class PublicClient:
    """Narrow public observation/action capability; no transport/evaluation accessor."""
    __slots__=('__client',)
    def __init__(self,client):self.__client=client
    @property
    def position(self):return self.__client.position
    @property
    def channel(self):return self.__client.channel
    def enter(self):return self.__client.enter()
    def measure(self,*a,**kw):return self.__client.measure(*a,**kw)
    def clear(self,*a,**kw):return self.__client.clear(*a,**kw)
    def exit(self):return self.__client.exit()
    def metrics(self):return self.__client.metrics()

def dump(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2))

def audit_new(folder):
    case=json.loads((folder/'evaluator_hidden_case.json').read_text())
    truth={s['channel']:np.array([s['x'],s['y']]) for s in case['sources']}
    events=list(map(json.loads,(folder/'strategy.jsonl').read_text().splitlines()))
    counts={}
    for e in events:
        kind=e['type'];counts[kind]=counts.get(kind,0)+1
        if kind not in ('feasible_update','certified_measure','certified_clear','range_bracket'):
            continue
        v=np.asarray(e['vertices']);g=truth[e['channel']]
        assert len(v)>0 and np.isfinite(v).all()
        edges=np.roll(v,-1,axis=0)-v;delta=g-v
        cross=edges[:,0]*delta[:,1]-edges[:,1]*delta[:,0]
        assert np.all(cross>=-1e-4) or np.all(cross<=1e-4),('source excluded',e)
        if kind=='range_bracket':
            z=(g-np.asarray(e['first']))@np.asarray(e['axis'])
            assert e['lower']-1e-6<=z<=e['upper']+1e-6
        if kind in ('certified_measure','certified_clear'):
            p=np.asarray(e['point']);radius=e['radius']
            assert np.linalg.norm(v-p,axis=1).max()<=radius+1e-8
            assert radius<(1000 if kind=='certified_measure' else 20)
    return counts

def aggregate(rows,reference='BASE'):
    groups={n:[r for r in rows if r['variant']==n] for n in sorted({r['variant'] for r in rows})}
    ref={r['case_id']:r for r in groups[reference]}
    result={}
    for n,rs in groups.items():
        t=[r['penalized_virtual_s'] for r in rs]
        deltas=[(r['penalized_virtual_s']/ref[r['case_id']]['penalized_virtual_s']-1,r['case_id']) for r in rs]
        result[n]=dict(runs=len(rs),complete=sum(r['success'] for r in rs),
            failed=sum(not r['success'] for r in rs),timeouts=sum(r['timeout'] for r in rs),
            false_complete=sum(r['false_complete'] for r in rs),
            mean=float(np.mean(t)),p95=float(np.percentile(t,95)),maximum=max(t),
            worst_case=rs[int(np.argmax(t))]['case_id'],worst_paired_regression=max(deltas),
            clearance_ratio_mean=float(np.mean([r['cleared']/r['total'] for r in rs])),
            raw_mean=float(np.mean([r['metrics']['virtual_time_s'] for r in rs])),
            movement_detection_etc={k:float(np.mean([r['metrics']['components'][k] for r in rs])) for k in rs[0]['metrics']['components']},
            phase_means={k:float(np.mean([r['metrics']['phases'].get(k,0) for r in rs])) for k in sorted(set().union(*(r['metrics']['phases'] for r in rs)))},
            mean_per_cleared=float(np.mean([r['metrics']['virtual_time_s']/max(1,r['cleared']) for r in rs])),
            wall_p95=float(np.percentile([r['elapsed_wall_s'] for r in rs],95)),
            clear_failure_mean=float(np.mean([r['metrics']['counts']['clear_failure'] for r in rs])))
    for n,v in result.items():
        v['mean_change_pct']=100*(v['mean']/result[reference]['mean']-1)
        v['significant']=n!=reference and v['mean_change_pct']<=-5 and v['complete']>=result[reference]['complete'] and v['p95']<=result[reference]['p95']
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--round',required=True);p.add_argument('--variants',default='BASE,HOMING')
    p.add_argument('--rounding',default='bounded',choices=['bounded','pre_round_stress'])
    p.add_argument('--fixtures');p.add_argument('--limit',type=int)
    p.add_argument('--stage',default='development');p.add_argument('--label')
    args=p.parse_args()
    rounddir=ROOT/args.round
    out=rounddir/(args.label or args.rounding)
    out.mkdir(parents=True,exist_ok=False)
    baseline=json.loads((ROOT/'frozen/question3/configs/recommended_omni.json').read_text())
    names=args.variants.split(',')
    configs={n:(baseline if n=='BASE' else dict(baseline_config=baseline,mechanism=n.lower())) for n in names}
    dump(out/'configs.json',configs)
    manifest={str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest() for x in ROOT.glob('*.py')}
    dump(out/'code_sha256.json',manifest)
    for file in ROOT.glob('*.py'):
        dest=out/'code_snapshot'/file.name;dest.parent.mkdir(exist_ok=True);shutil.copy2(file,dest)
    cases=json.loads(Path(args.fixtures).read_text()) if args.fixtures else list(development_cases())
    if args.limit:cases=cases[:args.limit]
    dump(out/'fixtures.json',cases)
    dump(out/'metadata.json',dict(stage=args.stage,rounding=args.rounding,
        distinct_layouts=len({json.dumps(c['sources'],sort_keys=True) for c in cases}),
        case_sha256={c['id']:hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest() for c in cases},
        official_runs=0,formal_runs=0,numeric_parameter_search_trials=0))
    rows=[]
    for i,case in enumerate(cases):
        order=names[i%len(names):]+names[:i%len(names)]
        for name in order:
            folder=out/name/case['id'];folder.mkdir(parents=True)
            dump(folder/'evaluator_hidden_case.json',case)
            log=JsonlLog(folder/'actions.jsonl');events=JsonlLog(folder/'strategy.jsonl')
            env=Simulator(case,rounding=args.rounding)
            client=Client(env,'SELF',log,5.)
            start=time.perf_counter()
            try:
                result=(baseline_run if name=='BASE' else candidate_run)(PublicClient(client),configs[name],events)
            except Exception as exc:
                result=dict(status='incomplete',failure=f'{type(exc).__name__}: {exc}',metrics=client.metrics(),regions=[])
            wall=time.perf_counter()-start
            truth=env.evaluation()  # First evaluator access, after the policy returned.
            row=dict(variant=name,case_id=case['id'],stage=args.stage,rounding=args.rounding,
                status=result['status'],failure=result.get('failure'),elapsed_wall_s=wall,
                total=truth['total'],cleared=truth['cleared'],metrics=result['metrics'])
            row['false_complete']=result['status']=='complete' and bool(truth['remaining_channels'])
            row['timeout']=bool(result.get('failure') and any(x in result['failure'].lower() for x in ('deadline','timeout','budget')))
            row['success']=result['status']=='complete' and not truth['remaining_channels']
            dump(folder/'result.json',dict(summary=row,strategy=result))
            log.close();events.close()
            try:
                if row['success']:
                    if name.startswith('COVER_'):
                        from .coverage_audit import audit as coverage_audit
                        row['audited_actions']=coverage_audit(folder)
                    else:row['audited_actions']=audit_folder(folder)
                    row['event_counts']=audit_new(folder)
                    row['audit']='pass'
                else:row['audit']='incomplete retained'
            except Exception as exc:
                row['audit']=f'FAIL {type(exc).__name__}: {exc}'
                row['success']=False;row['false_complete']=True
            row['penalized_virtual_s']=truth['virtual_time_s'] if row['success'] else max(360000,truth['virtual_time_s'])
            dump(folder/'result.json',dict(summary=row,strategy=result))
            rows.append(row)
        dump(out/'summary.json',dict(rows=rows,aggregates=aggregate(rows)))
        print(f'{i+1}/{len(cases)} {case["id"]} '+', '.join(f'{r["variant"]}={r["penalized_virtual_s"]:.1f}'+(' '+str(r['failure'])+' '+r['audit'] if not r['success'] else '') for r in rows[-len(names):]),flush=True)
    stats=aggregate(rows);dump(out/'comparison.json',stats)
    print(json.dumps({n:{k:v[k] for k in ('complete','runs','mean','mean_change_pct','p95','maximum','significant')} for n,v in stats.items()},indent=2),flush=True)

if __name__=='__main__':main()
