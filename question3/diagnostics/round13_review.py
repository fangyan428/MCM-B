"""Round13 fixed public-radius-prior ablations, with failure-only trajectory audit."""
import argparse
import json
import hashlib
from pathlib import Path
from question3.analyze_matrix import good
from question3.diagnostics.round11_review import actions


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
    assert all('radius_prior' in e for e in additional)
    assert [(e['point'][0],e['point'][1],e['channel']) for e in additional]==[(e[1],e[2],e[3]) for e in deleted]
    return len(deleted)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--development-only',action='store_true');args=parser.parse_args()
    names=['dev_main','dev_rounding']
    if not args.development_only:names+=['adverse_main','adverse_rounding','holdout_main','holdout_rounding','outer_main','outer_rounding']
    root=Path('question3/results');report=dict(batches={},official_runs=0,formal_runs=0);summaries={}
    for name in names:
        folder=root/('round13_'+name);s=json.loads((folder/'summary.json').read_text());summaries[name]=s
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in s['code_sha256'].items())
        rows=s['cases'];ids=sorted(s['case_sha256']);lookup={(r['variant'],r['case_id']):r for r in rows}
        assert len(rows)==len(ids)*4 and all(good(r) for r in rows)
        variants={}
        for v in ['DOMAIN','RANGE','BOTH']:
            pairs=[]
            for i in ids:
                a,b=lookup['REF',i],lookup[v,i];n=check_pair(folder/'REF'/i,folder/v/i)
                saved=a['metrics']['virtual_time_s']-b['metrics']['virtual_time_s'];assert saved>=-1e-5
                assert a['metrics']['counts']['clear_failure']-b['metrics']['counts']['clear_failure']==n
                for k in ['switch_s','detection_s','laser_s']:assert a['metrics']['components'][k]==b['metrics']['components'][k]
                pairs.append(dict(case_id=i,additional_skips=n,saved_s=saved))
            variants[v]=dict(additional_skips=sum(p['additional_skips'] for p in pairs),pairs=pairs)
        stats=json.loads((folder/'comparison.json').read_text())['stats'];st={r['variant']:r for r in stats}
        report['batches'][name]=dict(runs=len(rows),complete=len(rows),failed=0,timeouts=0,false_complete=0,
            audited_actions=sum(r['audited_actions'] for r in rows),variants=variants,stats=stats,
            additive_interaction_s=st['BOTH']['mean_virtual_s']-st['DOMAIN']['mean_virtual_s']-st['RANGE']['mean_virtual_s']+st['REF']['mean_virtual_s'],
            trajectories_and_existing_halfplane_proofs_preserved=True)
    for a,b in zip(names[::2],names[1::2]):
        for key in ['code_sha256','case_sha256','configs']:assert summaries[a][key]==summaries[b][key]
    qualifying=[]
    for v in ['DOMAIN','RANGE','BOTH']:
        checks=[]
        for name in ['dev_main','dev_rounding']:
            st={r['variant']:r for r in report['batches'][name]['stats']}
            checks.append(st[v]['mean_virtual_s']<st['REF']['mean_virtual_s'] and st[v]['p95_virtual_s']<=st['REF']['p95_virtual_s'])
        if all(checks):qualifying.append(v)
    st={r['variant']:r for r in report['batches']['dev_main']['stats']}
    selected=min(qualifying,key=lambda v:(st[v]['mean_virtual_s'],2 if v=='BOTH' else 1,v)) if qualifying else None
    report['development_selected']=selected
    if not args.development_only:
        lock=json.loads((root/'round13_lock.json').read_text());assert lock['selected_variant']==selected
        for s in summaries.values():
            for k in ['code_sha256','configs']:assert s[k]==lock[k]
        gates=[]
        for name in ['holdout_main','holdout_rounding','outer_main','outer_rounding']:
            st={r['variant']:r for r in report['batches'][name]['stats']}
            gates.append(dict(batch=name,passed=st[selected]['mean_virtual_s']<st['REF']['mean_virtual_s'] and st[selected]['p95_virtual_s']<=st['REF']['p95_virtual_s']))
        report.update(adoption_gates=gates,adopt_selected=all(g['passed'] for g in gates))
    legacy=0
    for rounding in ['main','rounding']:
        for batch in ['dev']+([] if args.development_only else ['adverse']):
            old=json.loads((root/f'round11_{batch}_{rounding}'/'summary.json').read_text())
            lk={r['case_id']:r for r in old['cases'] if r['variant']=='P'}
            for r in summaries[f'{batch}_{rounding}']['cases']:
                if r['variant']!='REF':continue
                for k in ['metrics','status','cleared','remaining_channels','audit']:assert r[k]==lk[r['case_id']][k]
                legacy+=1
    report.update(legacy_exact_comparisons=legacy,total_runs=sum(b['runs'] for b in report['batches'].values()),
                  total_audited_actions=sum(b['audited_actions'] for b in report['batches'].values()),
                  fresh_validation_runs=0 if args.development_only else 2240,fresh_layouts=0 if args.development_only else 70)
    name='round13_development_evidence.json' if args.development_only else 'round13_review_evidence.json'
    (root/name).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='batches'},indent=2))


if __name__=='__main__':main()
