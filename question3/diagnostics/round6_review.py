"""Round6 development gates, all failures retained; no fresh validation performed."""
import hashlib
import json
from pathlib import Path
from question3.analyze_matrix import good


def main():
    root=Path('question3/results');names=['round6_dev_main','round6_dev_rounding',
        'round6_factorial_main','round6_factorial_rounding','round6_adverse_main','round6_adverse_rounding']
    result=dict(kind='SELF_ROUND6_DEVELOPMENT_REVIEW',batches={},fresh_validation_runs=0,official_runs=0,formal_runs=0)
    summaries={}
    for name in names:
        s=json.loads((root/name/'summary.json').read_text());summaries[name]=s
        assert len(s['cases'])==len(s['configs'])*len(s['case_sha256'])
        counts={}
        for v in s['configs']:
            decisions=changes=reversed_paths=0;entry_saved=0.
            for path in (root/name/v).glob('*/strategy.jsonl'):
                for line in path.read_text().splitlines():
                    e=json.loads(line)
                    decisions+=e.get('cache_routing')=='station_insertion'
                    changes+=e.get('cache_order_changed',False)
                    if e['type']=='optical_path_order':
                        reversed_paths+=e['reversed'];entry_saved+=e['entry_distance_saved_m']
            counts[v]=dict(cache_insertion_decisions=decisions,changed_orders=changes,
                           reversed_paths=reversed_paths,local_entry_distance_saved_m=entry_saved)
        rows=s['cases'];result['batches'][name]=dict(kind=s['kind'],runs=len(rows),
            complete=sum(good(r) for r in rows),failed=sum(not good(r) for r in rows),
            timeouts=sum(r['timeout'] for r in rows),false_complete=sum(r['false_complete'] for r in rows),
            audited_actions=sum(r.get('audited_actions',0) for r in rows),mechanism_counts=counts)
    gates=[]
    for v in ['I','V','IV']:
        checks=[]
        for name in ['round6_factorial_main','round6_factorial_rounding']:
            stats={r['variant']:r for r in json.loads((root/name/'comparison.json').read_text())['stats']}
            a,b=stats['REF'],stats[v]
            checks.append(dict(batch=name,mean_delta_s=b['mean_virtual_s']-a['mean_virtual_s'],
                p95_delta_s=b['p95_virtual_s']-a['p95_virtual_s'],
                passed=b['complete']==b['runs'] and b['mean_virtual_s']<a['mean_virtual_s'] and b['p95_virtual_s']<=a['p95_virtual_s']))
        gates.append(dict(variant=v,passed=all(c['passed'] for c in checks),checks=checks))
    result['development_gates']=gates;result['promoted']=None
    assert not any(g['passed'] for g in gates),'Reassess: a candidate passed the declared gate'
    n=0
    for suffix in ['main','rounding']:
        old=json.loads((root/f'round5_dev_{suffix}'/'summary.json').read_text())
        lookup={r['case_id']:r for r in old['cases'] if r['variant']=='COMPACT_BATCH'}
        for row in summaries[f'round6_factorial_{suffix}']['cases']:
            if row['variant']=='REF':
                prior=lookup[row['case_id']]
                for k in ['metrics','status','cleared','remaining_channels','audit']:assert row[k]==prior[k]
                n+=1
    result['unchanged_recommended_exact_run_comparisons']=n
    for a,b in zip(names[::2],names[1::2]):
        for key in ['case_sha256','configs','code_sha256']:assert summaries[a][key]==summaries[b][key]
    lock=json.loads((root/'round6_adverse_lock.json').read_text())
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in lock['code_sha256'].items())
    result['total_runs']=sum(b['runs'] for b in result['batches'].values())
    result['total_audited_actions']=sum(b['audited_actions'] for b in result['batches'].values())
    (root/'round6_review_evidence.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='batches'},indent=2))


if __name__=='__main__':main()
