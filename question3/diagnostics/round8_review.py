"""Round8 fixed candidate audit, including sampled-geometry and global-time tradeoffs."""
import hashlib
import json
from pathlib import Path
import numpy as np
from question3.analyze_matrix import good,objective


def main():
    root=Path('question3/results');lock=json.loads((root/'round8_lock.json').read_text())
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in lock['code_sha256'].items())
    names=['round8_dev_main','round8_dev_rounding','round8_adverse_main','round8_adverse_rounding',
           'round8_holdout_main','round8_holdout_rounding','round8_outer_main','round8_outer_rounding']
    report=dict(selected_before_validation='Z',batches={},code_lock_unchanged=True,
                official_runs=0,formal_runs=0,fresh_validation_runs=1680,fresh_layouts=70)
    summaries={};legacy=0
    for name in names:
        d=root/name;s=json.loads((d/'summary.json').read_text());summaries[name]=s
        rows=s['cases'];ids=sorted(s['case_sha256']);lookup={(r['variant'],r['case_id']):r for r in rows}
        assert len(rows)==len(ids)*len(s['configs']);variants={}
        for v in s['configs']:
            records=[]
            for i in ids:
                for e in map(json.loads,(d/v/i/'strategy.jsonl').read_text().splitlines()):
                    if e['type']=='localization' and e['selection']['mode']=='opportunistic_current':
                        t=e['selection'];records.append(dict(case_id=i,channel=e['channel'],
                            current_sampled_diameter=t['sampled_worst_diameter'],catalog_sampled_diameter=t['catalog_sampled_diameter'],
                            proxy_delta_s=t['score_s']-t['catalog_score_s'],local_catalog_movement_m=t['catalog_entry_distance_m'],
                            actual_clear_plan_points=e['planned_clear_calls']))
            rs=[lookup[v,i] for i in ids];keys=set().union(*(r['metrics']['phases'] for r in rs))
            variants[v]=dict(opportunity_count=len(records),cases_with_opportunities=len({r['case_id'] for r in records}),
                accepted_worse_proxy=sum(r['proxy_delta_s']>1e-8 for r in records),
                accepted_larger_sampled_diameter=sum(r['current_sampled_diameter']>r['catalog_sampled_diameter']+1e-7 for r in records),
                sum_local_catalog_movement_m=sum(r['local_catalog_movement_m'] for r in records),
                max_sampled_diameter_m=max((r['current_sampled_diameter'] for r in records),default=None),
                records=records,mean_phases={k:float(np.mean([r['metrics']['phases'].get(k,0) for r in rs])) for k in sorted(keys)})
        pairs=[]
        for v in ['J','Z']:
            a=np.array([objective(lookup['REF',i]) for i in ids]);b=np.array([objective(lookup[v,i]) for i in ids]);gain=1-b/a;k=int(np.argmin(gain))
            pairs.append(dict(variant=v,mean_saved_s=float((a-b).mean()),mean_gain=1-float(b.mean()/a.mean()),
                wins=int(sum(gain>1e-9)),losses=int(sum(gain< -1e-9)),ties=int(sum(abs(gain)<=1e-9)),
                worst_gain=float(gain[k]),worst_case=ids[k],worst_times_s=[float(a[k]),float(b[k])]))
        report['batches'][name]=dict(runs=len(rows),complete=sum(good(r) for r in rows),failed=sum(not good(r) for r in rows),
            timeouts=sum(r['timeout'] for r in rows),false_complete=sum(r['false_complete'] for r in rows),
            audited_actions=sum(r.get('audited_actions',0) for r in rows),variants=variants,pairs=pairs)
    for a,b in zip(names[::2],names[1::2]):
        for k in ['case_sha256','code_sha256','configs']:assert summaries[a][k]==summaries[b][k]
    for name in names[2:]:
        assert summaries[name]['code_sha256']==lock['code_sha256'];assert summaries[name]['configs']==lock['configs']
    for suffix in ['main','rounding']:
        old=json.loads((root/f'round7_count_{suffix}'/'summary.json').read_text())
        lookup={r['case_id']:r for r in old['cases'] if r['variant']=='K'}
        for r in summaries[f'round8_dev_{suffix}']['cases']:
            if r['variant']=='REF':
                for k in ['metrics','status','cleared','remaining_channels','audit']:assert r[k]==lookup[r['case_id']][k]
                legacy+=1
    gates=[]
    for name in names[4:]:
        stats={r['variant']:r for r in json.loads((root/name/'comparison.json').read_text())['stats']}
        a,b=stats['REF'],stats['Z']
        gates.append(dict(batch=name,passed=b['complete']==b['runs'] and b['mean_virtual_s']<a['mean_virtual_s'] and b['p95_virtual_s']<=a['p95_virtual_s'],
            mean_change_s=b['mean_virtual_s']-a['mean_virtual_s'],p95_change_s=b['p95_virtual_s']-a['p95_virtual_s']))
    report.update(adoption_checks=gates,adopt_selected=all(g['passed'] for g in gates),legacy_exact_comparisons=legacy,
        total_runs=sum(b['runs'] for b in report['batches'].values()),total_audited_actions=sum(b['audited_actions'] for b in report['batches'].values()))
    (root/'round8_review_evidence.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='batches'},indent=2))


if __name__=='__main__':main()
