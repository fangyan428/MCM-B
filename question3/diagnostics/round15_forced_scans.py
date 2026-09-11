"""Reconstruct ready-cache entry scores at forced scans from recorded public data.
Score gaps are not simulated or guaranteed total-time savings.
"""
import json
import math
from pathlib import Path
import numpy as np


def inspect(folder):
    requests={};seen=set();actions=[];bearings={}
    for e in map(json.loads,(folder/'actions.jsonl').read_text().splitlines()):
        if e['type']=='request':requests[e['payload']['request_id']]=e
        if e['type']!='response' or not e['response'].get('accepted'):continue
        rid=e['request_id']
        if rid in seen:continue
        seen.add(rid);q=requests[rid];b=q['payload'];r=e['response']
        if q['path'] not in ('/measure','/clear'):continue
        p=(b['position']['x'],b['position']['y'])
        actions.append(dict(path=q['path'],phase=q['phase'],p=p,c=b['channel'],success=r.get('clear_result')=='success'))
        if r.get('measure_result')=='direction':bearings[p,b['channel']]=r['svd_deg']
    result=json.loads((folder/'result.json').read_text())['strategy'];cover=result['station_positions']
    regions={};cached={};index=0;position=(0.,0.);records=[]
    for e in map(json.loads,(folder/'strategy.jsonl').read_text().splitlines()):
        if e['type']=='localization':regions[e['channel']]=e
        if e['type']=='shared_cache_store':
            c=e['channel'];region=regions[c]
            if 'vertices' not in region:entry=tuple(region['second_position'])
            else:
                first=region['first_position'];a=math.radians(bearings[tuple(first),c])
                R=np.array([[math.cos(a),-math.sin(a)],[math.sin(a),math.cos(a)]])
                local=(np.array(region['vertices'])-first)@R;lo=local.min(axis=0)-1e-5;hi=local.max(axis=0)+1e-5
                size=np.maximum(1,np.ceil((hi-lo)/28).astype(int))
                entry=tuple(np.array(first)+R@(lo+(.5/size)*(hi-lo)))
            cached[c]=entry
        if e['type']=='shared_cache_use':cached.pop(e['channel'])
        if e['type']!='schedule':continue
        if e['task']=='scan':
            station=tuple(cover[e['station_id']])
            if e.get('forced') and cached:
                c,q=min(cached.items(),key=lambda item:(math.dist(position,item[1]),item[0]))
                records.append(dict(station_id=e['station_id'],position=position,cached_channel=c,
                    scan_entry_m=math.dist(position,station),cache_entry_m=math.dist(position,q),
                    entry_score_gap_s=(math.dist(position,station)-math.dist(position,q))/5))
            while index<len(actions) and actions[index]['phase'] in ('search','near') and actions[index]['p']==station:
                position=actions[index]['p'];index+=1
        else:
            target=e['channel']
            while index<len(actions):
                action=actions[index];position=action['p'];index+=1
                if action['path']=='/clear' and action['c']==target and action['success']:break
            else:raise AssertionError('Missing task completion')
    assert index==len(actions)
    return records


def main():
    result=dict(kind='OFFLINE_PUBLIC_ENTRY_SCORE_DIAGNOSTIC_NOT_POLICY_RESULT',batches={})
    for suffix in ['dev_main','dev_rounding']:
        root=Path('question3/results')/('round15_'+suffix);summary=json.loads((root/'summary.json').read_text());rows=[]
        config=summary['configs']['REF']
        assert config['optical_cell_m']==28 and config.get('optical_order','original')=='original'
        assert not config['modules'].get('D',False) and not config['modules'].get('C',False)
        for r in summary['cases']:
            if r['variant']!='REF':continue
            for e in inspect(root/'REF'/r['case_id']):rows.append(dict(case_id=r['case_id'],**e))
        positive=[e for e in rows if e['entry_score_gap_s']>1e-7]
        result['batches'][suffix]=dict(forced_scans_with_ready_cache=len(rows),closer_cache_bypassed=len(positive),
            affected_cases=len({e['case_id'] for e in positive}),records=rows)
    Path('question3/results/round15_forced_scan_scores.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({n:{k:v for k,v in b.items() if k!='records'} for n,b in result['batches'].items()},indent=2))


if __name__=='__main__':main()
