"""Reproduce the fixed selective-sharing decision; reused cases are not holdouts."""
import hashlib
import json
from pathlib import Path
from question3.analyze_matrix import good


def main():
    root=Path('question3/results')
    lock=json.loads((root/'round10_adverse_lock.json').read_text())
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in lock['code_sha256'].items())
    evidence=dict(kind='SELF_ROUND10_DEVELOPMENT_AND_REUSED_ADVERSE',batches={},
                  fresh_validation_runs=0,official_runs=0,formal_runs=0,legacy_exact_comparisons=0)
    summaries={}
    for suffix in ['dev_main','dev_rounding','adverse_main','adverse_rounding']:
        path=root/('round10_'+suffix);s=json.loads((path/'summary.json').read_text());summaries[suffix]=s
        assert s['code_sha256']==lock['code_sha256'] and s['configs']==lock['configs']
        rows=s['cases'];assert len(rows)==len(s['case_sha256'])*3
        stats=json.loads((path/'comparison.json').read_text())['stats'];variants={}
        for v in s['configs']:
            rs=[r for r in rows if r['variant']==v];keys=set().union(*(r['metrics']['phases'] for r in rs))
            opportunities=sharing=0
            for r in rs:
                es=list(map(json.loads,(path/v/r['case_id']/'strategy.jsonl').read_text().splitlines()))
                cs={e['channel'] for e in es if e['type']=='localization' and e['selection']['mode']=='opportunistic_current'}
                opportunities+=len(cs)
                sharing+=sum(e['type']=='shared_cache_store' and e['primary_channel'] in cs for e in es)
            variants[v]=dict(opportunities=opportunities,current_extra_sharing=sharing,
                mean_phases={k:sum(r['metrics']['phases'].get(k,0) for r in rs)/len(rs) for k in sorted(keys)})
        evidence['batches'][suffix]=dict(stats=stats,variants=variants,runs=len(rows),
            complete=sum(good(r) for r in rows),failed=sum(not good(r) for r in rows),
            timeouts=sum(r['timeout'] for r in rows),false_complete=sum(r['false_complete'] for r in rows),
            audited_actions=sum(r.get('audited_actions',0) for r in rows))
        rounding=suffix.rsplit('_',1)[1]
        old={}
        for batch in ['dev','adverse','holdout','outer']:
            data=json.loads((root/f'round9_{batch}_{rounding}'/'summary.json').read_text())
            old.update({r['case_id']:r for r in data['cases'] if r['variant']=='ZL'})
        for r in rows:
            if r['variant']=='REF':
                previous=old[r['case_id']]
                for k in ['metrics','status','cleared','remaining_channels','audit']:assert r[k]==previous[k]
                evidence['legacy_exact_comparisons']+=1
    for a,b in [('dev_main','dev_rounding'),('adverse_main','adverse_rounding')]:
        for k in ['code_sha256','case_sha256','configs']:assert summaries[a][k]==summaries[b][k]
    gates=[]
    for v in ['CS0','CS1']:
        checks=[]
        for suffix in ['dev_main','dev_rounding']:
            stats={r['variant']:r for r in evidence['batches'][suffix]['stats']};a,b=stats['REF'],stats[v]
            checks.append(dict(batch=suffix,passed=b['complete']==b['runs'] and b['mean_virtual_s']<a['mean_virtual_s'] and b['p95_virtual_s']<=a['p95_virtual_s'],
                mean_delta_s=b['mean_virtual_s']-a['mean_virtual_s'],p95_delta_s=b['p95_virtual_s']-a['p95_virtual_s']))
        gates.append(dict(variant=v,checks=checks,eligible=all(c['passed'] for c in checks)))
    evidence.update(development_gates=gates,selected_new_candidate=None,
                    recommendation='Retain round9 ZL; neither new candidate passes development gates.',
                    total_runs=sum(b['runs'] for b in evidence['batches'].values()),
                    total_audited_actions=sum(b['audited_actions'] for b in evidence['batches'].values()),
                    external_fixture_counter_note='run_matrix calls all external fixtures unseen; these 12 cases are explicitly reused, so fresh_validation_runs is zero.')
    assert not any(g['eligible'] for g in gates)
    (root/'round10_review_evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps({k:v for k,v in evidence.items() if k!='batches'},indent=2))


if __name__=='__main__':main()
