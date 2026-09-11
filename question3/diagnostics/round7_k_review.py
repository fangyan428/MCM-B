"""Independent second-stage validation after selecting K; no parameter changes."""
import hashlib
import json
from pathlib import Path
import numpy as np
from question3.analyze_matrix import good,objective


def main():
    root=Path('question3/results');lock=json.loads((root/'round7_k_lock.json').read_text())
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in lock['code_sha256'].items())
    names=['round7_k_holdout_main','round7_k_holdout_rounding','round7_k_outer_main','round7_k_outer_rounding']
    report=dict(selected='K',code_lock_unchanged=True,prior_DK_rejected=True,batches={},
                official_runs=0,formal_runs=0,new_independent_layouts=70)
    gates=[];low_count_checks=0;summaries={}
    for name in names:
        d=root/name;s=json.loads((d/'summary.json').read_text());summaries[name]=s
        assert s['code_sha256']==lock['code_sha256'];assert s['configs']==lock['configs']
        ids=sorted(s['case_sha256']);rows=s['cases'];lookup={(r['variant'],r['case_id']):r for r in rows}
        assert len(rows)==2*len(ids);a=[lookup['REF',i] for i in ids];b=[lookup['K',i] for i in ids]
        before=np.array([objective(r) for r in a]);after=np.array([objective(r) for r in b]);gain=1-after/before
        stats={r['variant']:r for r in json.loads((d/'comparison.json').read_text())['stats']}
        gates.append(dict(batch=name,passed=all(good(r) for r in b) and after.mean()<before.mean()
            and stats['K']['p95_virtual_s']<=stats['REF']['p95_virtual_s'],mean_gain=1-float(after.mean()/before.mean())))
        groups={}
        for n in sorted({r['total'] for r in a}):
            ii=[j for j,r in enumerate(a) if r['total']==n]
            groups[str(n)]=dict(runs=len(ii),reference_mean_s=float(before[ii].mean()),candidate_mean_s=float(after[ii].mean()),
                mean_saved_s=float((before[ii]-after[ii]).mean()),wins=int(sum(gain[ii]>1e-9)),losses=int(sum(gain[ii]< -1e-9)))
        certificates=discoveries=0;phase_keys=set().union(*(r['metrics']['phases'] for r in rows))
        for i in ids:
            if lookup['REF',i]['total']<16:
                assert lookup['REF',i]['metrics']==lookup['K',i]['metrics'];low_count_checks+=1
            result=json.loads((d/'K'/i/'result.json').read_text())['strategy']
            certificates+=(result.get('stopping_certificate') or {}).get('method')=='source_count_upper_bound'
            for e in map(json.loads,(d/'K'/i/'strategy.jsonl').read_text().splitlines()):
                discoveries+=e['type']=='source_upper_bound_saturated'
        report['batches'][name]=dict(runs=len(rows),complete=sum(good(r) for r in rows),failed=sum(not good(r) for r in rows),
            timeouts=sum(r['timeout'] for r in rows),false_complete=sum(r['false_complete'] for r in rows),
            audited_actions=sum(r.get('audited_actions',0) for r in rows),count_certificates=certificates,
            saturation_events=discoveries,source_count_groups=groups,wins=int(sum(gain>1e-9)),losses=int(sum(gain< -1e-9)),
            ties=int(sum(abs(gain)<=1e-9)),mean_saved_s=float((before-after).mean()),worst_gain=float(gain.min()),
            worst_case=ids[int(np.argmin(gain))],
            mean_phases={v:{k:float(np.mean([r['metrics']['phases'].get(k,0) for r in rs])) for k in sorted(phase_keys)} for v,rs in [('REF',a),('K',b)]})
    for a,b in zip(names[::2],names[1::2]):
        for k in ['case_sha256','code_sha256','configs']:assert summaries[a][k]==summaries[b][k]
    previous=json.loads((root/'round7_review_evidence.json').read_text())
    report.update(adoption_checks=gates,adopt_selected=all(g['passed'] for g in gates),
        final_independent_validation_runs=sum(x['runs'] for x in report['batches'].values()),
        total_round7_runs=previous['total_runs']+sum(x['runs'] for x in report['batches'].values()),
        total_round7_audited_actions=previous['total_audited_actions']+sum(x['audited_actions'] for x in report['batches'].values()),
        fewer_than_16_exact_comparisons=low_count_checks)
    (root/'round7_k_review_evidence.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='batches'},indent=2))


if __name__=='__main__':main()
