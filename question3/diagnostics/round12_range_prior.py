"""Read-only next-mechanism diagnostic. Never reads source coordinates or radii."""
import json
import math
from pathlib import Path


def main():
    rows=[]
    for suffix in ['dev_main','dev_rounding','adverse_main','adverse_rounding']:
        root=Path('question3/results')/('round12_'+suffix)
        summary=json.loads((root/'summary.json').read_text());count=0;cases=set();details=[]
        for row in summary['cases']:
            if row['variant']!='REF':continue
            folder=root/'REF'/row['case_id'];regions={}
            for e in map(json.loads,(folder/'strategy.jsonl').read_text().splitlines()):
                if e['type']=='localization':regions[e['channel']]=e
            requests={};seen=set()
            for e in map(json.loads,(folder/'actions.jsonl').read_text().splitlines()):
                if e['type']=='request':requests[e['payload']['request_id']]=e
                if e['type']!='response' or e['response'].get('accepted') is not True:continue
                rid=e['request_id']
                if rid in seen:continue
                seen.add(rid);q=requests[rid]
                if q['path']!='/clear':continue
                c=q['payload']['channel'];region=regions.get(c)
                if region is None:continue
                p=tuple(q['payload']['position'][k] for k in ['x','y'])
                circles=[((0,0),1800),(region['first_position'],1500),(region['second_position'],1500)]
                reasons=[i for i,(o,r) in enumerate(circles) if math.dist(p,o)>r+20+1e-5]
                if reasons:
                    assert e['response']['clear_result']=='no_target_in_range'
                    count+=1;cases.add(row['case_id']);details.append(dict(case_id=row['case_id'],channel=c,point=p,circle_indices=reasons))
        rows.append(dict(batch=suffix,additional_failed_clear_calls_with_public_radius_separation=count,cases=len(cases),details=details))
    result=dict(kind='OFFLINE_PUBLIC_GEOMETRY_DIAGNOSTIC_NOT_STRATEGY_TRIAL',rows=rows,
        notes='Published domain1800 and detection upper radius1500, using known first/second points. Existing accepted clear calls only; no proposed policy executed.')
    Path('question3/results/round12_range_prior_opportunities.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps([dict(batch=r['batch'],calls=r['additional_failed_clear_calls_with_public_radius_separation']) for r in rows]))


if __name__=='__main__':main()
