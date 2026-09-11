"""Four-way paired evidence, actual complete clearance and full regression lists."""
import hashlib
import json
from pathlib import Path
from question3.analyze_matrix import good


def main():
    root=Path('question3/results');lock=json.loads((root/'round19_lock.json').read_text())
    report=dict(batches={},selected=lock['selected_variant'],total_runs=0,total_audited_actions=0,legacy_exact=0,
        fresh_validation_runs=2240,fresh_layouts=70,official_runs=0,formal_runs=0)
    summaries={};variants=['REF','PRIMARY','SHARED','BOTH']
    for name in ['dev_main','dev_rounding','adverse_main','adverse_rounding','holdout_main','holdout_rounding','outer_main','outer_rounding']:
        folder=root/('round19_'+name);s=json.loads((folder/'summary.json').read_text());summaries[name]=s;rows=s['cases']
        assert len(rows)==len(s['case_sha256'])*4 and all(good(r) for r in rows)
        for k in ['configs','code_sha256']:assert s[k]==lock[k]
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in s['code_sha256'].items())
        task_stats={};domain_stats={}
        for v in variants:
            counts=dict(domain_cost_proxy=0,domain_current=0,domain_shared=0);max_tasks=0;shared=0
            for row in rows:
                if row['variant']!=v:continue
                es=list(map(json.loads,(folder/v/row['case_id']/'strategy.jsonl').read_text().splitlines()))
                tasks=[e for e in es if e['type']=='schedule'];scans=[e['station_id'] for e in tasks if e['task']=='scan'];locs=[e['channel'] for e in tasks if e['task']=='localize']
                assert len(scans)==len(set(scans))<=7 and len(locs)==len(set(locs))<=16 and len(tasks)<=23
                assert not any(e['forced'] for e in tasks);max_tasks=max(max_tasks,len(tasks))
                shared+=sum(e['type']=='shared_cache_store' for e in es)
                for e in es:
                    if e['type']=='localization' and e['selection']['mode'] in counts:counts[e['selection']['mode']]+=1
            rs=[r for r in rows if r['variant']==v];keys=set().union(*(r['metrics']['phases'] for r in rs))
            task_stats[v]=dict(max_tasks=max_tasks,shared_cache_stores=shared,
                mean_phases={k:sum(r['metrics']['phases'].get(k,0) for r in rs)/len(rs) for k in sorted(keys)})
            domain_stats[v]=counts
        if name.startswith(('dev','adverse')):
            suffix=name.split('_')[1];old=[]
            for prefix in (['dev'] if name.startswith('dev') else ['dev','adverse','holdout','outer']):
                old+=json.loads((root/('round18_'+prefix+'_'+suffix)/'summary.json').read_text())['cases']
            old={(r['variant'],r['case_id']):r for r in old}
            for r in rows:
                if r['variant'] in ['REF','PRIMARY']:
                    o=old['REF' if r['variant']=='REF' else 'DOMAIN',r['case_id']]
                    for k in ['metrics','status','cleared','remaining_channels','audit']:assert r[k]==o[k]
                    report['legacy_exact']+=1
        stats=json.loads((folder/'comparison.json').read_text())['stats'];st={r['variant']:r for r in stats}
        by={(r['variant'],r['case_id']):r for r in rows};regressions={v:[] for v in variants[1:]};interactions=[]
        for i in sorted(s['case_sha256']):
            times={v:by[v,i]['metrics']['virtual_time_s'] for v in variants}
            interactions.append(dict(case=i,interaction_s=times['BOTH']-times['PRIMARY']-times['SHARED']+times['REF']))
            for v in variants[1:]:
                a,b=by['REF',i],by[v,i];ta=times['REF'];tb=times[v]
                if tb>ta+1e-7:regressions[v].append(dict(case=i,ref_s=ta,variant_s=tb,increase_pct=100*(tb/ta-1),
                    component_delta_s={k:b['metrics']['components'][k]-a['metrics']['components'][k] for k in a['metrics']['components']}))
        batch=dict(runs=len(rows),complete=len(rows),failures=0,timeouts=0,false_complete=0,
            stats=stats,task_stats=task_stats,domain_stats=domain_stats,
            all_regressions={v:sorted(rs,key=lambda r:r['increase_pct'],reverse=True) for v,rs in regressions.items()},
            interaction=dict(mean_s=sum(r['interaction_s'] for r in interactions)/len(interactions),negative_count=sum(r['interaction_s']<-1e-7 for r in interactions),positive_count=sum(r['interaction_s']>1e-7 for r in interactions),cases=interactions),
            gates={v:st[v]['mean_virtual_s']<st['REF']['mean_virtual_s'] and st[v]['p95_virtual_s']<=st['REF']['p95_virtual_s'] for v in variants[1:]})
        if name.startswith('outer'):
            batch['generator_groups_post_run_only']={}
            for parity,label in [(0,'uniform_angles'),(1,'clustered_angles')]:
                batch['generator_groups_post_run_only'][label]={}
                for v in variants:
                    a=[r for r in rows if r['variant']==v and int(r['case_id'].split('_')[2])%2==parity]
                    batch['generator_groups_post_run_only'][label][v]=dict(cases=len(a),mean_s=sum(r['metrics']['virtual_time_s'] for r in a)/len(a))
        report['batches'][name]=batch
        report['total_runs']+=len(rows);report['total_audited_actions']+=sum(r['audited_actions'] for r in rows)
    for prefix in ['dev','adverse','holdout','outer']:
        for k in ['case_sha256','configs','code_sha256']:assert summaries[prefix+'_main'][k]==summaries[prefix+'_rounding'][k]
    selected=lock['selected_variant']
    report['adoption_checks']=[dict(batch=n,passed=report['batches'][n]['gates'][selected]) for n in ['holdout_main','holdout_rounding','outer_main','outer_rounding']]
    report['adopt_selected']=all(c['passed'] for c in report['adoption_checks'])
    (root/'round19_review_evidence.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='batches'},indent=2))


if __name__=='__main__':main()
