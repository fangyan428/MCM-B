"""Whole-flow phase comparison. Entry bound is never treated as total-time dominance."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from question3.analyze_matrix import good
from question3.diagnostics.round11_review import actions


def prefix_before_outer(folder):
    requests={};seen=set();trace=[]
    for e in map(json.loads,(folder/'actions.jsonl').read_text().splitlines()):
        if e['type']=='request':requests[e['payload']['request_id']]=e
        if e['type']!='response' or not e['response'].get('accepted'):continue
        rid=e['request_id']
        if rid in seen:continue
        seen.add(rid);q=requests[rid];b=q['payload'];r=e['response']
        if q['path'] not in ('/measure','/clear'):continue
        p=(b['position']['x'],b['position']['y'])
        if q['path']=='/measure' and q['phase']=='search' and math.hypot(*p)>1e-7:break
        trace.append((q['path'],p,b['channel'],r.get('measure_result',r.get('clear_result')),r.get('svd_deg')))
    return trace


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--development-only',action='store_true');args=parser.parse_args()
    names=['dev_main','dev_rounding']
    if not args.development_only:names+=['adverse_main','adverse_rounding','holdout_main','holdout_rounding','outer_main','outer_rounding']
    root=Path('question3/results');report=dict(batches={},official_runs=0,formal_runs=0);summaries={}
    for name in names:
        folder=root/('round14_'+name);s=json.loads((folder/'summary.json').read_text());summaries[name]=s
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in s['code_sha256'].items())
        rows=s['cases'];ids=sorted(s['case_sha256']);lk={(r['variant'],r['case_id']):r for r in rows}
        assert len(rows)==2*len(ids) and all(good(r) for r in rows)
        pairs=[];phase_count=0;noop=0
        for i in ids:
            a,b=lk['REF',i],lk['PHASE',i]
            assert prefix_before_outer(folder/'REF'/i)==prefix_before_outer(folder/'PHASE'/i)
            events=[e for e in map(json.loads,(folder/'PHASE'/i/'strategy.jsonl').read_text().splitlines()) if e['type']=='ring_phase_selected']
            assert len(events)<=1;phase_count+=len(events)
            local=events[0]['local_movement_saved_s'] if events else 0
            assert local>=-1e-7
            is_noop=not events or math.hypot(*events[0]['position'])<=1e-9
            if is_noop:
                assert a['metrics']==b['metrics'];assert actions(folder/'REF'/i)==actions(folder/'PHASE'/i);noop+=1
            if name.startswith('outer'):assert is_noop
            pairs.append(dict(case_id=i,local_entry_saved_s=local,total_saved_s=a['metrics']['virtual_time_s']-b['metrics']['virtual_time_s'],noop=is_noop))
        stats=json.loads((folder/'comparison.json').read_text())['stats'];st={r['variant']:r for r in stats}
        keys=set().union(*(r['metrics']['phases'] for r in rows))
        phase_means={v:{k:sum(lk[v,i]['metrics']['phases'].get(k,0) for i in ids)/len(ids) for k in sorted(keys)} for v in ['REF','PHASE']}
        report['batches'][name]=dict(runs=len(rows),complete=len(rows),failed=0,timeouts=0,false_complete=0,
            audited_actions=sum(r['audited_actions'] for r in rows),stats=stats,pairs=pairs,phase_selections=phase_count,whole_trace_noops=noop,
            mean_local_entry_saved_s=sum(p['local_entry_saved_s'] for p in pairs)/len(ids),mean_phases=phase_means,
            passed_gate=(noop==len(ids)) if name.startswith('outer') else st['PHASE']['mean_virtual_s']<st['REF']['mean_virtual_s'] and st['PHASE']['p95_virtual_s']<=st['REF']['p95_virtual_s'])
    for a,b in zip(names[::2],names[1::2]):
        for k in ['code_sha256','case_sha256','configs']:assert summaries[a][k]==summaries[b][k]
    legacy=initial_exact=0;initial_runs=initial_audits=0
    for suffix in ['main','rounding']:
        for batch in ['dev']+([] if args.development_only else ['adverse']):
            old=json.loads((root/f'round13_{batch}_{suffix}'/'summary.json').read_text());lk={r['case_id']:r for r in old['cases'] if r['variant']=='BOTH'}
            for r in summaries[f'{batch}_{suffix}']['cases']:
                if r['variant']!='REF':continue
                for k in ['metrics','status','cleared','remaining_channels','audit']:assert r[k]==lk[r['case_id']][k]
                legacy+=1
        initial=json.loads((root/f'round14_initial_dev_{suffix}'/'summary.json').read_text())
        lk={(r['variant'],r['case_id']):r for r in initial['cases']}
        assert all(good(r) for r in initial['cases'])
        initial_runs+=len(lk);initial_audits+=sum(r['audited_actions'] for r in initial['cases'])
        for r in summaries[f'dev_{suffix}']['cases']:
            for k in ['metrics','status','cleared','remaining_channels','audit']:assert r[k]==lk[r['variant'],r['case_id']][k]
            initial_exact+=1
    if not args.development_only:
        lock=json.loads((root/'round14_lock.json').read_text())
        for s in summaries.values():
            for k in ['code_sha256','configs']:assert s[k]==lock[k]
        checks=[dict(batch=n,passed=report['batches'][n]['passed_gate']) for n in ['holdout_main','holdout_rounding','outer_main','outer_rounding']]
        report.update(adoption_checks=checks,adopt_selected=all(c['passed'] for c in checks))
    report.update(selected='PHASE',legacy_exact_comparisons=legacy,initial_rerun_exact_comparisons=initial_exact,
        primary_runs=sum(b['runs'] for b in report['batches'].values()),initial_retained_runs=initial_runs,
        total_runs=initial_runs+sum(b['runs'] for b in report['batches'].values()),
        total_audited_actions=initial_audits+sum(b['audited_actions'] for b in report['batches'].values()),
        fresh_validation_runs=0 if args.development_only else 1120,fresh_layouts=0 if args.development_only else 70)
    name='round14_development_evidence.json' if args.development_only else 'round14_review_evidence.json'
    (root/name).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='batches'},indent=2))


if __name__=='__main__':main()
