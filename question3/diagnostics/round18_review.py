"""Frozen paired validation, all regressions and post-run mechanism diagnostics."""
import hashlib
import json
from pathlib import Path
from question3.analyze_matrix import good


def main():
    root=Path('question3/results');lock=json.loads((root/'round18_lock.json').read_text())
    report=dict(batches={},total_runs=0,total_audited_actions=0,legacy_exact=0,
        fresh_validation_runs=1120,fresh_layouts=70,official_runs=0,formal_runs=0)
    summaries={}
    for name in ['dev_main','dev_rounding','adverse_main','adverse_rounding','holdout_main','holdout_rounding','outer_main','outer_rounding']:
        folder=root/('round18_'+name);s=json.loads((folder/'summary.json').read_text());summaries[name]=s;rows=s['cases']
        assert all(good(r) for r in rows)
        for k in ['configs','code_sha256']:assert s[k]==lock[k]
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in s['code_sha256'].items())
        task_stats={};domain_stats={}
        for v in ['REF','DOMAIN']:
            records=[];max_tasks=0;shared=0
            for row in rows:
                if row['variant']!=v:continue
                es=list(map(json.loads,(folder/v/row['case_id']/'strategy.jsonl').read_text().splitlines()))
                tasks=[e for e in es if e['type']=='schedule'];scans=[e['station_id'] for e in tasks if e['task']=='scan'];locs=[e['channel'] for e in tasks if e['task']=='localize']
                assert len(scans)==len(set(scans))<=7 and len(locs)==len(set(locs))<=16 and len(tasks)<=23
                assert not any(e['forced'] for e in tasks);max_tasks=max(max_tasks,len(tasks))
                shared+=sum(e['type']=='shared_cache_store' for e in es)
                for e in es:
                    if e['type']=='localization' and e['selection']['mode'].startswith('domain_'):
                        records.append(dict(case=row['case_id'],channel=e['channel'],**e['selection']))
            rs=[r for r in rows if r['variant']==v];keys=set().union(*(r['metrics']['phases'] for r in rs))
            task_stats[v]=dict(max_tasks=max_tasks,shared_cache_stores=shared,
                mean_phases={k:sum(r['metrics']['phases'].get(k,0) for r in rs)/len(rs) for k in sorted(keys)})
            domain_stats[v]=dict(total_uses=len(records),current_uses=sum(r['mode']=='domain_current' for r in records),records=records)
        if name.startswith(('dev','adverse')):
            suffix=name.split('_')[1]
            old=json.loads((root/('round17_dev_'+suffix)/'summary.json').read_text())['cases']
            if name.startswith('adverse'):old+=json.loads((root/('round17_adverse_'+suffix)/'summary.json').read_text())['cases']
            old={r['case_id']:r for r in old if r['variant']=='REF'}
            for r in rows:
                if r['variant']=='REF':
                    for k in ['metrics','status','cleared','remaining_channels','audit']:assert r[k]==old[r['case_id']][k]
                    report['legacy_exact']+=1
        stats=json.loads((folder/'comparison.json').read_text())['stats'];st={r['variant']:r for r in stats}
        by={(r['variant'],r['case_id']):r for r in rows};regressions=[]
        for i in sorted({r['case_id'] for r in rows}):
            a,b=by['REF',i],by['DOMAIN',i];ta=a['metrics']['virtual_time_s'];tb=b['metrics']['virtual_time_s']
            if tb>ta+1e-7:regressions.append(dict(case=i,ref_s=ta,domain_s=tb,increase_pct=100*(tb/ta-1),
                component_delta_s={k:b['metrics']['components'][k]-a['metrics']['components'][k] for k in a['metrics']['components']}))
        batch=dict(runs=len(rows),complete=len(rows),failures=0,timeouts=0,false_complete=0,
            stats=stats,task_stats=task_stats,domain_stats=domain_stats,all_regressions=sorted(regressions,key=lambda r:r['increase_pct'],reverse=True),
            passed_gate=st['DOMAIN']['mean_virtual_s']<st['REF']['mean_virtual_s'] and st['DOMAIN']['p95_virtual_s']<=st['REF']['p95_virtual_s'])
        if name.startswith('outer'):
            batch['generator_groups_post_run_only']={}
            for parity,label in [(0,'uniform_angles'),(1,'clustered_angles')]:
                g={}
                for v in ['REF','DOMAIN']:
                    a=[r for r in rows if r['variant']==v and int(r['case_id'].split('_')[2])%2==parity]
                    g[v]=dict(cases=len(a),mean_s=sum(r['metrics']['virtual_time_s'] for r in a)/len(a))
                batch['generator_groups_post_run_only'][label]=g
        report['batches'][name]=batch
        report['total_runs']+=len(rows);report['total_audited_actions']+=sum(r['audited_actions'] for r in rows)
    for prefix in ['dev','adverse','holdout','outer']:
        for k in ['case_sha256','configs','code_sha256']:assert summaries[prefix+'_main'][k]==summaries[prefix+'_rounding'][k]
    report['adoption_checks']=[dict(batch=n,passed=report['batches'][n]['passed_gate']) for n in ['holdout_main','holdout_rounding','outer_main','outer_rounding']]
    report['adopt_selected']=all(c['passed'] for c in report['adoption_checks'])
    (root/'round18_review_evidence.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='batches'},indent=2))


if __name__=='__main__':main()
