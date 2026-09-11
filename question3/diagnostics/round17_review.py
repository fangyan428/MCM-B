"""Independent post-run brute-force route and finite-stop review. No policy use."""
import hashlib
import itertools
import json
import math
from pathlib import Path
from question3.analyze_matrix import good


def path_cost(position,cover,path):
    total=0.
    for k in path:total+=math.dist(position,cover[k]);position=cover[k]
    return total


def inspect(folder):
    requests={};seen=set();actions=[]
    for e in map(json.loads,(folder/'actions.jsonl').read_text().splitlines()):
        if e['type']=='request':requests[e['payload']['request_id']]=e
        if e['type']!='response' or not e['response'].get('accepted'):continue
        rid=e['request_id']
        if rid in seen:continue
        seen.add(rid);req=requests[rid];b=req['payload'];res=e['response']
        if req['path'] not in ('/measure','/clear'):continue
        actions.append(dict(path=req['path'],phase=req['phase'],p=(b['position']['x'],b['position']['y']),c=b['channel'],
            success=res.get('clear_result')=='success',signal=res.get('measure_result') in ('direction','near')))
    result=json.loads((folder/'result.json').read_text())['strategy'];cover=result['station_positions']
    i=0;position=(0.,0.);known=set();cleared=set();visited=set();records=[]
    def consume():
        nonlocal i,position
        a=actions[i];i+=1;position=a['p']
        if a['signal'] or a['success']:known.add(a['c'])
        if a['success']:cleared.add(a['c'])
        return a
    for e in map(json.loads,(folder/'strategy.jsonl').read_text().splitlines()):
        if e['type']!='schedule':continue
        remaining=[] if len(known)==16 else sorted(set(range(7))-visited)
        route=e['scan_route'];assert set(route)==set(remaining) and len(route)==len(remaining)
        actual=path_cost(position,cover,route);best=min(path_cost(position,cover,p) for p in itertools.permutations(remaining))
        assert abs(actual-e['scan_route_cost_m'])<1e-7 and abs(actual-best)<1e-7
        greedy=[];p=position;left=remaining.copy()
        while left:
            k=min(left,key=lambda k:(math.dist(p,cover[k]),k));greedy.append(k);p=cover[k];left.remove(k)
        records.append(dict(task=e['task'],target=e.get('channel',e.get('station_id')),position=position,
            route=route,greedy=greedy,static_saving_s=(path_cost(position,cover,greedy)-best)/5,
            first_changed=bool(route) and route[0]!=greedy[0],known=len(known),pending_channels=sorted(known-cleared)))
        if e['task']=='scan':
            assert route[0]==e['station_id'];station=tuple(cover[e['station_id']]);assert e['station_id'] not in visited
            while i<len(actions) and actions[i]['phase'] in ('search','near') and actions[i]['p']==station:consume()
            visited.add(e['station_id'])
        else:
            while i<len(actions):
                a=consume()
                if a['path']=='/clear' and a['c']==e['channel'] and a['success']:break
            else:raise AssertionError('No successful completion of localization')
    assert i==len(actions)
    return records


def main():
    root=Path('question3/results');report=dict(batches={},total_runs=0,total_audited_actions=0,legacy_exact=0,
        independent_validation_runs=0,official_runs=0,formal_runs=0)
    lock=json.loads((root/'round17_reused_lock.json').read_text())
    for name in ['dev_main','dev_rounding','adverse_main','adverse_rounding']:
        folder=root/('round17_'+name);s=json.loads((folder/'summary.json').read_text());rows=s['cases']
        assert all(good(r) for r in rows)
        for k in ['configs','code_sha256']:assert s[k]==lock[k]
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in s['code_sha256'].items())
        old=json.loads((root/('round16_'+name)/'summary.json').read_text())['cases']
        if name.startswith('adverse'):old+=json.loads((root/('round16_holdout_'+name.split('_')[1])/'summary.json').read_text())['cases']
        old={r['case_id']:r for r in old if r['variant']=='FREE'}
        route_records={};task_count=0
        for row in rows:
            i=row['case_id'];v=row['variant'];f=folder/v/i
            es=list(map(json.loads,(f/'strategy.jsonl').read_text().splitlines()));tasks=[e for e in es if e['type']=='schedule']
            scans=[e['station_id'] for e in tasks if e['task']=='scan'];locs=[e['channel'] for e in tasks if e['task']=='localize']
            assert len(scans)==len(set(scans))<=7 and len(locs)==len(set(locs))<=16 and len(tasks)<=23
            assert not any(e['forced'] for e in tasks)
            if v=='REF':
                for k in ['metrics','status','cleared','remaining_channels','audit']:assert row[k]==old[i][k]
                report['legacy_exact']+=1
            else:route_records[i]=inspect(f);task_count+=len(route_records[i])
        stats=json.loads((folder/'comparison.json').read_text())['stats'];st={r['variant']:r for r in stats}
        by={(r['variant'],r['case_id']):r for r in rows};regressions=[]
        for i in sorted(route_records):
            a,b=by['REF',i],by['ROUTE',i];ta=a['metrics']['virtual_time_s'];tb=b['metrics']['virtual_time_s']
            if tb>ta+1e-7:regressions.append(dict(case=i,ref_s=ta,route_s=tb,increase_pct=100*(tb/ta-1),
                component_delta_s={k:b['metrics']['components'][k]-a['metrics']['components'][k] for k in a['metrics']['components']}))
        report['batches'][name]=dict(runs=len(rows),complete=len(rows),failures=0,timeouts=0,false_complete=0,
            stats=stats,verified_scheduling_routes=task_count,route_records=route_records,
            all_regressions=sorted(regressions,key=lambda r:r['increase_pct'],reverse=True),
            passed_gate=st['ROUTE']['mean_virtual_s']<st['REF']['mean_virtual_s'] and st['ROUTE']['p95_virtual_s']<=st['REF']['p95_virtual_s'])
        report['total_runs']+=len(rows);report['total_audited_actions']+=sum(r['audited_actions'] for r in rows)
    for prefix in ['dev','adverse']:
        a=json.loads((root/('round17_'+prefix+'_main')/'summary.json').read_text())
        b=json.loads((root/('round17_'+prefix+'_rounding')/'summary.json').read_text())
        for k in ['case_sha256','configs','code_sha256']:assert a[k]==b[k]
    report['development_passed']=all(report['batches'][n]['passed_gate'] for n in ['dev_main','dev_rounding'])
    (root/'round17_review_evidence.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='batches'},indent=2))


if __name__=='__main__':main()
