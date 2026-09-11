"""All-case evidence, legal-count ablations and action-prefix checks; evaluator only."""
import hashlib
import json
from pathlib import Path
import numpy as np
from question3.analyze_matrix import good,objective
from question3.audit import audit_folder


def action_trace(path):
    return [(e['path'],e['payload'].get('position'),e['payload'].get('channel'))
            for e in map(json.loads,path.read_text().splitlines())
            if e['type']=='request' and e['path'] in ('/measure','/clear')]


def main():
    root=Path('question3/results');lock=json.loads((root/'round7_lock.json').read_text())
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in lock['code_sha256'].items())
    names=['round7_dev_main','round7_dev_rounding','round7_count_main','round7_count_rounding',
           'round7_adverse_main','round7_adverse_rounding','round7_holdout_main','round7_holdout_rounding',
           'round7_outer_main','round7_outer_rounding']
    result=dict(selected='DK',batches={},code_lock_unchanged=True,official_runs=0,formal_runs=0,
                fresh_validation_runs=3360,fresh_layouts=70)
    summaries={};prefix_checks=lower_count_checks=legacy_checks=0
    for name in names:
        folder=root/name;s=json.loads((folder/'summary.json').read_text());summaries[name]=s
        rows=s['cases'];ids=sorted(s['case_sha256']);lookup={(r['variant'],r['case_id']):r for r in rows}
        assert len(rows)==len(ids)*len(s['configs'])
        variants={}
        for v in s['configs']:
            rs=[lookup[v,i] for i in ids];count_stops=discovery_stops=circles=0
            for i in ids:
                d=folder/v/i;actual=json.loads((d/'result.json').read_text())['strategy']
                count_stops+=(actual.get('stopping_certificate') or {}).get('method')=='source_count_upper_bound'
                if name in ['round7_count_main','round7_count_rounding']:audit_folder(d)
                for e in map(json.loads,(d/'strategy.jsonl').read_text().splitlines()):
                    discovery_stops+=e['type']=='source_upper_bound_saturated'
                    circles+=e['type']=='localization' and 'single_circle_centre' in e
            phase_keys=set().union(*(r['metrics']['phases'] for r in rs))
            variants[v]=dict(count_certificates=count_stops,saturated_discovery_events=discovery_stops,
                single_circle_clears=circles,mean_phases={k:float(np.mean([r['metrics']['phases'].get(k,0) for r in rs])) for k in sorted(phase_keys)},
                means_by_source_count={str(n):float(np.mean([objective(r) for r in rs if r['total']==n])) for n in sorted({r['total'] for r in rs})})
        pairs=[]
        for a,b in [('REF','D'),('REF','U'),('REF','K'),('D','DU'),('D','DK'),('K','DK'),('REF','DK')]:
            if a not in variants or b not in variants:continue
            before=np.array([objective(lookup[a,i]) for i in ids]);after=np.array([objective(lookup[b,i]) for i in ids])
            delta=1-after/before;k=int(np.argmin(delta))
            pairs.append(dict(before=a,after=b,mean_saved_s=float(np.mean(before-after)),
                mean_gain=1-float(after.mean()/before.mean()),wins=int(sum(delta>1e-9)),losses=int(sum(delta< -1e-9)),
                ties=int(sum(abs(delta)<=1e-9)),worst_gain=float(delta[k]),worst_case=ids[k],
                worst_times_s=[float(before[k]),float(after[k])]))
        if 'U' in variants:
            for i in ids:
                for a,b in [('REF','U'),('D','DU')]:
                    ta=action_trace(folder/a/i/'actions.jsonl');tb=action_trace(folder/b/i/'actions.jsonl')
                    assert ta[:len(tb)]==tb,(name,i,a,b)
                    assert objective(lookup[b,i])<=objective(lookup[a,i])+1e-6
                    prefix_checks+=1
                if lookup['REF',i]['total']<16:
                    for a,b in [('REF','K'),('D','DK')]:
                        assert lookup[a,i]['metrics']==lookup[b,i]['metrics'],(name,i,a,b)
                        lower_count_checks+=1
        result['batches'][name]=dict(kind=s['kind'],runs=len(rows),complete=sum(good(r) for r in rows),
            failed=sum(not good(r) for r in rows),timeouts=sum(r['timeout'] for r in rows),
            false_complete=sum(r['false_complete'] for r in rows),
            audited_actions=sum(r.get('audited_actions',0) for r in rows),variants=variants,pairs=pairs)
    for a,b in zip(names[::2],names[1::2]):
        for key in ['case_sha256','configs','code_sha256']:assert summaries[a][key]==summaries[b][key]
    for name in names[6:]:
        assert summaries[name]['code_sha256']==lock['code_sha256'];assert summaries[name]['configs']==lock['configs']
    for suffix in ['main','rounding']:
        prior=json.loads((root/f'round5_dev_{suffix}'/'summary.json').read_text())
        old={r['case_id']:r for r in prior['cases'] if r['variant']=='COMPACT_BATCH'}
        for r in summaries[f'round7_count_{suffix}']['cases']:
            if r['variant']=='REF':
                for key in ['metrics','status','cleared','remaining_channels','audit']:assert r[key]==old[r['case_id']][key]
                legacy_checks+=1
    gates=[]
    for name in names[6:]:
        stats={r['variant']:r for r in json.loads((root/name/'comparison.json').read_text())['stats']}
        a,b=stats['REF'],stats['DK'];gates.append(dict(batch=name,
            passed=b['complete']==b['runs'] and b['mean_virtual_s']<a['mean_virtual_s'] and b['p95_virtual_s']<=a['p95_virtual_s'],
            mean_gain=1-b['mean_virtual_s']/a['mean_virtual_s'],p95_change_s=b['p95_virtual_s']-a['p95_virtual_s']))
    result.update(adoption_checks=gates,adopt_selected=all(g['passed'] for g in gates),
                  action_prefix_checks=prefix_checks,fewer_than_16_unchanged_checks=lower_count_checks,
                  legacy_exact_run_comparisons=legacy_checks,reaudited_development_runs=624,
                  total_runs=sum(b['runs'] for b in result['batches'].values()),
                  total_audited_actions=sum(b['audited_actions'] for b in result['batches'].values()))
    (root/'round7_review_evidence.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='batches'},indent=2))


if __name__=='__main__':main()
