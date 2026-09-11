"""Post-run attribution and public pending-queue evidence for the next experiment."""
import json
import math
from pathlib import Path


def initial_queue(folder):
    requests={};known=set();cleared=set()
    for e in map(json.loads,(folder/'actions.jsonl').read_text().splitlines()):
        if e['type']=='request':requests[e['payload']['request_id']]=e
        if e['type']!='response' or not e['response'].get('accepted'):continue
        q=requests[e['request_id']];r=e['response'];b=q['payload']
        if q['path']=='/measure':
            if q['phase']=='search' and math.hypot(b['position']['x'],b['position']['y'])>1e-7:break
            if r['measure_result']!='no_signal':known.add(b['channel'])
        if r.get('clear_result')=='success':cleared.add(b['channel'])
    cached=set()
    for e in map(json.loads,(folder/'strategy.jsonl').read_text().splitlines()):
        if e['type']=='schedule' and e['task']=='scan' and e['station_id']!=0:break
        if e['type']=='shared_cache_store':cached.add(e['channel'])
        if e['type']=='shared_cache_use':cached.discard(e['channel'])
    return dict(known=sorted(known),cleared=sorted(cleared),pending=sorted(known-cleared),cached=sorted(cached))


def main():
    root=Path('question3/results/round14_holdout_main');rows=[]
    for case in ['holdout_190046_smooth','holdout_190049_negative']:
        folders={v:root/v/case for v in ['REF','PHASE']}
        results={v:json.loads((p/'result.json').read_text())['summary'] for v,p in folders.items()}
        a,b=results['REF']['metrics'],results['PHASE']['metrics']
        e=next(e for e in map(json.loads,(folders['PHASE']/'strategy.jsonl').read_text().splitlines()) if e['type']=='ring_phase_selected')
        rows.append(dict(case_id=case,ref_s=a['virtual_time_s'],phase_s=b['virtual_time_s'],
            phase_event=e,public_queue_before_first_outer=initial_queue(folders['REF']),
            components_delta_s={k:b['components'][k]-a['components'][k] for k in a['components']},
            phases_delta_s={k:b['phases'].get(k,0)-a['phases'].get(k,0) for k in sorted(set(a['phases'])|set(b['phases']))},
            counts_delta={k:b['counts'][k]-a['counts'][k] for k in a['counts']}))
    report=dict(kind='POST_RUN_FAILURE_ATTRIBUTION_NOT_NEW_POLICY_RESULT',cases=rows,
        next_hypothesis='Keep the fixed ring; compare ending a known/cached localization batch before resuming search with the current nearest/forced-two interleaving. Published <=16 sources permits a finite batch, but total-time benefit remains untested.')
    Path('question3/results/round14_failure_attribution.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
