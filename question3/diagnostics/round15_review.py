"""Finite-batch audit and fixed development decision, retaining all regressions."""
import hashlib
import json
from pathlib import Path
from question3.analyze_matrix import good


def check_batches(folder):
    outstanding=None;queued=None;chain=[];steps=0;longest=0
    for e in map(json.loads,(folder/'strategy.jsonl').read_text().splitlines()):
        if e['type']=='localization_batch':
            current=set(e['batch_channels']);assert current and len(current)<=16
            if outstanding is not None:assert current==outstanding
            outstanding=current;queued=e;steps+=1
        if e['type']=='schedule':
            if queued:
                assert e['task']=='localize' and e['channel'] in outstanding
                outstanding=outstanding-{e['channel']}
                if not outstanding:outstanding=None
                queued=None
            if e['task']=='scan':
                assert outstanding is None;chain=[]
            else:
                assert e['channel'] not in chain;chain.append(e['channel'])
                longest=max(longest,len(chain));assert longest<=16
    assert outstanding is None and queued is None
    return steps,longest


def main():
    root=Path('question3/results');lock=json.loads((root/'round15_adverse_lock.json').read_text())
    names=['dev_main','dev_rounding','adverse_main','adverse_rounding'];report=dict(batches={},official_runs=0,formal_runs=0,fresh_validation_runs=0)
    summaries={};legacy=0
    for name in names:
        folder=root/('round15_'+name);s=json.loads((folder/'summary.json').read_text());summaries[name]=s
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in s['code_sha256'].items())
        for k in ['code_sha256','configs']:assert s[k]==lock[k]
        rows=s['cases'];ids=sorted(s['case_sha256']);lk={(r['variant'],r['case_id']):r for r in rows}
        assert len(rows)==len(ids)*3 and all(good(r) for r in rows)
        variants={}
        for v in s['configs']:
            stats=[check_batches(folder/v/i) for i in ids]
            keys=set().union(*(lk[v,i]['metrics']['phases'] for i in ids))
            variants[v]=dict(batch_steps=sum(p[0] for p in stats),longest_chain=max(p[1] for p in stats),
                mean_phases={k:sum(lk[v,i]['metrics']['phases'].get(k,0) for i in ids)/len(ids) for k in sorted(keys)})
        report['batches'][name]=dict(runs=len(rows),complete=len(rows),failed=0,timeouts=0,false_complete=0,
            audited_actions=sum(r['audited_actions'] for r in rows),variants=variants,
            stats=json.loads((folder/'comparison.json').read_text())['stats'])
        rounding=name.rsplit('_',1)[1];old={}
        for batch,variant in [('round13_dev','BOTH'),('round13_adverse','BOTH'),('round14_holdout','REF')]:
            previous=json.loads((root/(batch+'_'+rounding)/'summary.json').read_text())
            old.update({r['case_id']:r for r in previous['cases'] if r['variant']==variant})
        for r in rows:
            if r['variant']=='REF':
                for k in ['metrics','status','cleared','remaining_channels','audit']:assert r[k]==old[r['case_id']][k]
                legacy+=1
    for a,b in zip(names[::2],names[1::2]):
        for k in ['code_sha256','case_sha256','configs']:assert summaries[a][k]==summaries[b][k]
    gates=[]
    for v in ['CACHE','KNOWN']:
        checks=[]
        for name in ['dev_main','dev_rounding']:
            st={s['variant']:s for s in report['batches'][name]['stats']};a,b=st['REF'],st[v]
            checks.append(dict(batch=name,mean_delta_s=b['mean_virtual_s']-a['mean_virtual_s'],p95_delta_s=b['p95_virtual_s']-a['p95_virtual_s'],
                passed=b['mean_virtual_s']<a['mean_virtual_s'] and b['p95_virtual_s']<=a['p95_virtual_s']))
        gates.append(dict(variant=v,checks=checks,eligible=all(c['passed'] for c in checks)))
    assert not any(g['eligible'] for g in gates)
    report.update(development_gates=gates,selected_new_candidate=None,recommendation='Retain round13 BOTH; both batch candidates fail development gates.',
        total_runs=sum(b['runs'] for b in report['batches'].values()),total_audited_actions=sum(b['audited_actions'] for b in report['batches'].values()),
        legacy_exact_comparisons=legacy,fixture_note='External adverse fixtures are reused, not unseen validation, regardless of generic run_matrix counter name.')
    (root/'round15_review_evidence.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='batches'},indent=2))


if __name__=='__main__':main()
