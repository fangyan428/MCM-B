"""All-case evidence for the fixed problem-3 optimization and validation cycle."""
import hashlib
import json
from pathlib import Path
import numpy as np
from question3.analyze_matrix import good,objective


def main():
    root=Path('question3/results');lock=json.loads((root/'round4_lock.json').read_text());selected=lock['selected_variant']
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in lock['code_sha256'].items())
    names=['round4_dev_main','round4_dev_rounding','round4_adapt_main','round4_adapt_rounding','round4_holdout_main','round4_holdout_rounding','round4_outer_main','round4_outer_rounding']
    result=dict(selected=selected,code_lock_unchanged=True,batches={})
    summaries={}
    for name in names:
        d=root/name;s=json.loads((d/'summary.json').read_text());summaries[name]=s
        rows=s['cases'];ids=sorted({r['case_id'] for r in rows});variants={};lookup={(r['variant'],r['case_id']):r for r in rows}
        for v in s['configs']:
            rs=[lookup[v,i] for i in ids];switches=shares=gate_choices=gate_rejections=0
            for i in ids:
                for line in (d/v/i/'strategy.jsonl').read_text().splitlines():
                    e=json.loads(line)
                    switches+=e['type']=='search_ring_switch';shares+=e['type']=='shared_cache_store'
                    if e['type']=='shared_gate' and e['candidates']:
                        gate_choices+=e['selected_channel'] is not None;gate_rejections+=e['selected_channel'] is None
            phase_keys=sorted(set().union(*(r['metrics']['phases'] for r in rs)))
            variants[v]=dict(ring_switches=switches,shared_measurements=shares,gate_choices=gate_choices,gate_rejections=gate_rejections,
                cleared_across_runs=sum(r['cleared'] for r in rs),mean_phases={k:float(np.mean([r['metrics']['phases'].get(k,0) for r in rs])) for k in phase_keys})
        pairs=[]
        for a,b in [('AB','ABS'),('ABS','ABSG'),('ABS','ABSR1125'),('ABSR1125','ABSR1125E'),('ABR1125','ABSR1125'),('ABSR1125','ABSR1125G')]:
            if a not in variants or b not in variants:continue
            va=np.array([objective(lookup[a,i]) for i in ids]);vb=np.array([objective(lookup[b,i]) for i in ids]);g=1-vb/va;k=int(np.argmin(g))
            pairs.append(dict(before=a,after=b,mean_saved_s=float((va-vb).mean()),median_gain=float(np.median(g)),wins=int(np.sum(g>1e-9)),losses=int(np.sum(g< -1e-9)),ties=int(np.sum(abs(g)<=1e-9)),worst_gain=float(g[k]),worst_case=ids[k],worst_times_s=[float(va[k]),float(vb[k])]))
        result['batches'][name]=dict(kind=s['kind'],runs=len(rows),configurations=len(s['configs']),complete=sum(good(r) for r in rows),
            timeouts=sum(r['timeout'] for r in rows),false_complete=sum(r['false_complete'] for r in rows),actions_audited=sum(r.get('audited_actions',0) for r in rows),variants=variants,pairs=pairs)
    for a,b in zip(names[::2],names[1::2]):
        assert summaries[a]['case_sha256']==summaries[b]['case_sha256'];assert summaries[a]['configs']==summaries[b]['configs'];assert summaries[a]['code_sha256']==summaries[b]['code_sha256']
    for name in names[4:]:
        assert summaries[name]['code_sha256']==lock['code_sha256'];assert summaries[name]['configs']==lock['configs']
    adoption=[]
    for name in names[4:]:
        comparison=json.loads((root/name/'comparison.json').read_text());s={r['variant']:r for r in comparison['stats']};candidate=s[selected];base=s['AB']
        adoption.append(dict(batch=name,pass_criteria=(candidate['complete']==candidate['runs'] and candidate['timeouts']==0 and candidate['false_complete']==0 and candidate['mean_virtual_s']<base['mean_virtual_s'] and candidate['median_paired_improvement']>0 and candidate['p95_virtual_s']<=base['p95_virtual_s']),mean_reduction_fraction=1-candidate['mean_virtual_s']/base['mean_virtual_s']))
    result['adoption_checks']=adoption;result['adopt_selected']=all(x['pass_criteria'] for x in adoption)
    result['total_runs']=sum(b['runs'] for b in result['batches'].values());result['total_audited_actions']=sum(b['actions_audited'] for b in result['batches'].values())
    (root/'round4_review_evidence.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='batches'},indent=2))

if __name__=='__main__':main()
