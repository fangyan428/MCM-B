"""Audit both outcomes and the claimed failure-only action subsequence."""
import argparse
import hashlib
import json
from pathlib import Path
from question3.analyze_matrix import good


def actions(folder):
    req={};accepted=set();trace=[]
    for e in map(json.loads,(folder/'actions.jsonl').read_text().splitlines()):
        if e['type']=='request':req[e['payload']['request_id']]=e
        if e['type']!='response' or not e['response'].get('accepted'):continue
        rid=e['request_id']
        if rid in accepted:continue
        accepted.add(rid);q=req[rid];p=q['payload'];r=e['response']
        if q['path'] not in ('/measure','/clear'):continue
        trace.append((q['path'],p['position']['x'],p['position']['y'],p['channel'],
                      r.get('measure_result',r.get('clear_result')),r.get('svd_deg')))
    return trace


def check_pair(base,new):
    a,b=actions(base),actions(new);j=0;deleted=[]
    for item in b:
        while j<len(a) and a[j]!=item:
            assert a[j][0]=='/clear' and a[j][4]=='no_target_in_range'
            deleted.append(a[j]);j+=1
        assert j<len(a),'New action absent from original trace';j+=1
    assert j==len(a),'Unexpected original trailing actions'
    old_events=list(map(json.loads,(base/'strategy.jsonl').read_text().splitlines()))
    new_events=list(map(json.loads,(new/'strategy.jsonl').read_text().splitlines()))
    assert [e for e in old_events if e['type']=='schedule']==[e for e in new_events if e['type']=='schedule']
    omitted=[e for e in new_events if e['type']=='certified_clear_skip']
    key=lambda e:(e['point'][0],e['point'][1],e['channel'],e['original_index'])
    previous={key(e):e for e in old_events if e['type']=='certified_clear_skip'}
    current={key(e):e for e in omitted}
    assert all(current[k]==e for k,e in previous.items()),'Existing single-halfplane witnesses changed'
    additional=[e for e in omitted if key(e) not in previous]
    assert all('halfplane_weights' in e for e in additional)
    assert [(e['point'][0],e['point'][1],e['channel']) for e in additional]==[(e[1],e[2],e[3]) for e in deleted]
    return len(deleted)


def review(suffixes):
    root=Path('question3/results');report=dict(batches={},official_runs=0,formal_runs=0)
    for suffix in suffixes:
        path=root/('round12_'+suffix);s=json.loads((path/'summary.json').read_text());rows=s['cases']
        lookup={(r['variant'],r['case_id']):r for r in rows};ids=sorted(s['case_sha256'])
        assert len(rows)==2*len(ids) and all(good(r) for r in rows)
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in s['code_sha256'].items())
        skipped=0;pairs=[]
        for i in ids:
            a,b=lookup['REF',i],lookup['Q',i]
            n=check_pair(path/'REF'/i,path/'Q'/i);skipped+=n
            delta=b['metrics']['virtual_time_s']-a['metrics']['virtual_time_s']
            assert delta<=1e-5,(suffix,i,delta)
            assert a['metrics']['counts']['clear_failure']-b['metrics']['counts']['clear_failure']==n
            for key in ['switch_s','detection_s','laser_s']:assert a['metrics']['components'][key]==b['metrics']['components'][key]
            pairs.append(dict(case_id=i,skipped=n,saved_s=-delta))
        stats=json.loads((path/'comparison.json').read_text())['stats'];stat={r['variant']:r for r in stats}
        report['batches'][suffix]=dict(runs=len(rows),complete=len(rows),failed=0,timeouts=0,false_complete=0,
            audited_actions=sum(r['audited_actions'] for r in rows),deleted_proven_failures=skipped,
            passed_gate=stat['Q']['mean_virtual_s']<stat['REF']['mean_virtual_s'] and stat['Q']['p95_virtual_s']<=stat['REF']['p95_virtual_s'],
            stats=stats,pairs=pairs,measurement_success_and_schedule_trajectories_identical=True)
    for first,second in zip(suffixes[::2],suffixes[1::2]):
        a=json.loads((root/('round12_'+first)/'summary.json').read_text())
        b=json.loads((root/('round12_'+second)/'summary.json').read_text())
        for k in ['code_sha256','case_sha256','configs']:assert a[k]==b[k]
    report.update(total_runs=sum(b['runs'] for b in report['batches'].values()),
                  total_audited_actions=sum(b['audited_actions'] for b in report['batches'].values()),
                  all_gates_passed=all(b['passed_gate'] for b in report['batches'].values()))
    return report


def main():
    p=argparse.ArgumentParser();p.add_argument('--development-only',action='store_true');args=p.parse_args()
    names=['dev_main','dev_rounding']
    if not args.development_only:names+=['adverse_main','adverse_rounding']
    report=review(names)
    legacy=0
    for rounding in ['main','rounding']:
        old={}
        for batch in ['dev','adverse','holdout','outer']:
            data=json.loads(Path(f'question3/results/round11_{batch}_{rounding}/summary.json').read_text())
            old.update({r['case_id']:r for r in data['cases'] if r['variant']=='P'})
        for batch in (['dev'] if args.development_only else ['dev','adverse']):
            data=json.loads(Path(f'question3/results/round12_{batch}_{rounding}/summary.json').read_text())
            for r in data['cases']:
                if r['variant']!='REF':continue
                for k in ['metrics','status','cleared','remaining_channels','audit']:assert r[k]==old[r['case_id']][k]
                legacy+=1
    if not args.development_only:
        lock=json.loads(Path('question3/results/round12_adverse_lock.json').read_text())
        for name in names:
            summary=json.loads(Path(f'question3/results/round12_{name}/summary.json').read_text())
            for k in ['code_sha256','configs']:assert summary[k]==lock[k]
    report['legacy_exact_comparisons']=legacy
    report.update(fresh_validation_runs=0,fresh_layouts=0,selected_new_candidate=None,
                  recommendation='Retain round11 P: Q has zero additional skipped clear calls and zero virtual-time gain.',
                  external_fixture_note='Adverse cases are reused; run_matrix external-fixture counter is not a count of new validation cases.')
    out=Path('question3/results/round12_development_evidence.json' if args.development_only else 'question3/results/round12_review_evidence.json')
    out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='batches'},indent=2))


if __name__=='__main__':main()
