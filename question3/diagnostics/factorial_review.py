"""Reproducible S/O/D conditional effects and public-log diagnostics."""
import argparse
import itertools
import json
from pathlib import Path
import numpy as np
from question3.analyze_matrix import objective,good


def variant(modules):return 'AB'+''.join(m for m in 'SOD' if m in modules)


def main():
    p=argparse.ArgumentParser();p.add_argument('folder');args=p.parse_args();root=Path(args.folder)
    summary=json.loads((root/'summary.json').read_text());rows=summary['cases'];ids=sorted({r['case_id'] for r in rows})
    lookup={(r['variant'],r['case_id']):r for r in rows};stats={};effects=[];interaction=[]
    values={n:np.array([objective(lookup[n,i]) for i in ids]) for n in summary['configs']}
    for n in values:
        events=[];diameters=[];grids=[];shared_d=[];dedicated_d=[];shared=used=circles=changes=decisions=0;cache_age=[]
        for i in ids:
            es=[json.loads(l) for l in (root/n/i/'strategy.jsonl').read_text().splitlines()];count=0;store={}
            for e in es:
                if e['type']=='shared_cache_store':shared+=1;store[e['channel']]=count
                if e['type']=='shared_cache_use':used+=1;cache_age.append(count-store[e['channel']])
                if e['type']=='localization' and 'diameter' in e:
                    diameters.append(e['diameter']);grids.append(e['planned_clear_calls'])
                    (shared_d if e['selection']['mode']=='shared_certified' else dedicated_d).append(e['diameter'])
                    circles+=('single_circle_centre' in e)
                if e['type']=='schedule':
                    count+=1
                    if e['mode']=='same_task_order':decisions+=1;changes+=e['order_changed']
            if good(lookup[n,i]):
                final=json.loads((root/n/i/'result.json').read_text())['strategy']
                assert set(store)<=set(final['cleared_channels'])
        nr=[lookup[n,i] for i in ids];phase_keys=sorted(set().union(*(r['metrics']['phases'] for r in nr)))
        stats[n]=dict(shared_measurements=shared,cached_plans_used=used,single_circles=circles,
                      ordering_comparisons=decisions,ordering_changes=changes,
                      max_diameter_m=max(diameters),mean_diameter_m=float(np.mean(diameters)),
                      shared_mean_diameter_m=float(np.mean(shared_d)) if shared_d else None,
                      dedicated_mean_diameter_m=float(np.mean(dedicated_d)) if dedicated_d else None,
                      mean_planned_clear_calls=float(np.mean(grids)),
                      mean_cache_age_tasks=float(np.mean(cache_age)) if cache_age else None,
                      mean_phases={k:float(np.mean([r['metrics']['phases'].get(k,0) for r in nr])) for k in phase_keys},
                      complete=sum(good(r) for r in nr),audited_actions=sum(r.get('audited_actions',0) for r in nr))
    for m in 'SOD':
        other=[x for x in 'SOD' if x!=m]
        for size in range(3):
            for subset in itertools.combinations(other,size):
                a=variant(subset);b=variant(set(subset)|{m});g=1-values[b]/values[a];k=int(np.argmin(g))
                effects.append(dict(module=m,without=a,with_variant=b,mean_saved_s=float((values[a]-values[b]).mean()),
                    median_improvement=float(np.median(g)),wins=int(np.sum(g>1e-9)),losses=int(np.sum(g< -1e-9)),
                    worst_regression=float(max(0,-g.min())),worst_case=ids[k],worst_times=[float(values[a][k]),float(values[b][k])]))
    for a,b in itertools.combinations('SOD',2):
        k=values[variant([a,b])]-values[variant([a])]-values[variant([b])]+values['AB']
        interaction.append(dict(pair=a+b,mean_interaction_s=float(k.mean()),negative_means='savings exceed sum of single-module savings'))
    three=values['ABSOD']-values['ABSO']-values['ABSD']-values['ABOD']+values['ABS']+values['ABO']+values['ABD']-values['AB']
    report=dict(kind='DEVELOPMENT_ONLY_SOD_FACTORIAL',variants=stats,effects=effects,interactions=interaction,
                third_order_interaction_s=float(three.mean()),runs=len(rows),actions_audited=sum(s['audited_actions'] for s in stats.values()))
    (root/'mechanism_diagnostics.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
