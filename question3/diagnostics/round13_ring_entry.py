"""Public trajectory diagnostic: potential FIRST ring-entry movement saving only.
No rotated-ring policy is run; subsequent search and localization costs may change.
"""
import json
import math
from pathlib import Path


def main():
    report=dict(kind='OFFLINE_FIRST_RING_ENTRY_BOUND_NOT_POLICY_RESULT',batches={})
    for suffix in ['dev_main','dev_rounding']:
        root=Path('question3/results')/('round13_'+suffix)
        data=json.loads((root/'summary.json').read_text());rows=[]
        for r in data['cases']:
            if r['variant']!='REF':continue
            path=root/'REF'/r['case_id']/'actions.jsonl';requests={};seen=set();position=(0.,0.);entry=None
            for e in map(json.loads,path.read_text().splitlines()):
                if e['type']=='request':requests[e['payload']['request_id']]=e
                if e['type']!='response' or not e['response'].get('accepted'):continue
                rid=e['request_id']
                if rid in seen:continue
                seen.add(rid);q=requests[rid]
                if q['path'] not in ('/measure','/clear'):continue
                p=tuple(q['payload']['position'][k] for k in ['x','y'])
                if q['path']=='/measure' and q['phase']=='search' and math.hypot(*p)>1e-7:
                    radius=math.hypot(*p);old=math.dist(position,p);lower=abs(math.hypot(*position)-radius)
                    entry=dict(previous_position=position,original_station=p,local_move_saving_bound_s=(old-lower)/5)
                    break
                position=p
            rows.append(dict(case_id=r['case_id'],**(entry or dict(local_move_saving_bound_s=0,no_outer_scan=True))))
        report['batches'][suffix]=dict(cases=len(rows),cases_with_positive_local_bound=sum(r['local_move_saving_bound_s']>1e-7 for r in rows),
            mean_local_bound_s=sum(r['local_move_saving_bound_s'] for r in rows)/len(rows),
            maximum=max(rows,key=lambda r:r['local_move_saving_bound_s']),rows=rows)
    Path('question3/results/round13_ring_entry_opportunities.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({n:{k:v for k,v in b.items() if k!='rows'} for n,b in report['batches'].items()},indent=2))


if __name__=='__main__':main()
