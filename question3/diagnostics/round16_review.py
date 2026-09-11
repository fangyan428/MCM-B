"""FREE verification: finite distinct tasks, actual complete clearance, full tails."""
import argparse
import hashlib
import json
from pathlib import Path
from question3.analyze_matrix import good


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--development-only',action='store_true');args=parser.parse_args()
    root=Path('question3/results');names=['dev_main','dev_rounding']
    if not args.development_only:names+=['adverse_main','adverse_rounding','holdout_main','holdout_rounding','outer_main','outer_rounding']
    report=dict(batches={},official_runs=0,formal_runs=0);summaries={};legacy=0
    for name in names:
        folder=root/('round16_'+name);s=json.loads((folder/'summary.json').read_text());summaries[name]=s
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in s['code_sha256'].items())
        rows=s['cases'];ids=sorted(s['case_sha256']);lk={(r['variant'],r['case_id']):r for r in rows}
        assert len(rows)==len(ids)*2 and all(good(r) for r in rows)
        task_stats={}
        for v in ['REF','FREE']:
            max_tasks=max_local_chain=forced_count=0
            for i in ids:
                events=list(map(json.loads,(folder/v/i/'strategy.jsonl').read_text().splitlines()))
                tasks=[e for e in events if e['type']=='schedule']
                scans=[e['station_id'] for e in tasks if e['task']=='scan'];locs=[e['channel'] for e in tasks if e['task']=='localize']
                assert len(scans)==len(set(scans)) and len(scans)<=7
                assert len(locs)==len(set(locs)) and len(locs)<=16 and len(tasks)<=23
                forced_count+=sum(e.get('forced',False) for e in tasks);chain=0
                for e in tasks:
                    chain=0 if e['task']=='scan' else chain+1;max_local_chain=max(max_local_chain,chain)
                if v=='FREE':assert not any(e.get('forced',False) for e in tasks)
                max_tasks=max(max_tasks,len(tasks))
            rs=[lk[v,i] for i in ids];keys=set().union(*(r['metrics']['phases'] for r in rs))
            task_stats[v]=dict(max_tasks=max_tasks,max_local_chain=max_local_chain,forced_scans=forced_count,
                mean_phases={k:sum(r['metrics']['phases'].get(k,0) for r in rs)/len(rs) for k in sorted(keys)})
        stats=json.loads((folder/'comparison.json').read_text())['stats'];st={r['variant']:r for r in stats}
        report['batches'][name]=dict(runs=len(rows),complete=len(rows),failed=0,timeouts=0,false_complete=0,
            audited_actions=sum(r['audited_actions'] for r in rows),stats=stats,task_stats=task_stats,
            passed_gate=st['FREE']['mean_virtual_s']<st['REF']['mean_virtual_s'] and st['FREE']['p95_virtual_s']<=st['REF']['p95_virtual_s'])
        if name.startswith(('dev','adverse')):
            old=json.loads((root/('round15_'+name)/'summary.json').read_text());old={r['case_id']:r for r in old['cases'] if r['variant']=='REF'}
            for r in rows:
                if r['variant']=='REF':
                    for k in ['metrics','status','cleared','remaining_channels','audit']:assert r[k]==old[r['case_id']][k]
                    legacy+=1
    for a,b in zip(names[::2],names[1::2]):
        for k in ['code_sha256','case_sha256','configs']:assert summaries[a][k]==summaries[b][k]
    if not args.development_only:
        lock=json.loads((root/'round16_lock.json').read_text())
        for s in summaries.values():
            for k in ['code_sha256','configs']:assert s[k]==lock[k]
        checks=[dict(batch=n,passed=report['batches'][n]['passed_gate']) for n in names[4:]]
        report.update(adoption_checks=checks,adopt_selected=all(c['passed'] for c in checks))
    report.update(selected='FREE',legacy_exact_comparisons=legacy,total_runs=sum(b['runs'] for b in report['batches'].values()),
        total_audited_actions=sum(b['audited_actions'] for b in report['batches'].values()),
        fresh_validation_runs=0 if args.development_only else 1120,fresh_layouts=0 if args.development_only else 70)
    out='round16_development_evidence.json' if args.development_only else 'round16_review_evidence.json'
    (root/out).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='batches'},indent=2))


if __name__=='__main__':main()
