"""Read-only public-state opportunities for extending the range certificate to S.

Counts are potential eligibility, not extra independent sources or time savings.
No altered policy is executed here and evaluator source locations are never read.
"""
import json
from pathlib import Path
from question2.strategy import candidate
from question3.current_point import local_offset
from question3.domain_range import range_upper,certified


def inspect(folder,config):
    requests={};accepted=set();first={};cleared=set();cached=set();records=[]
    for e in map(json.loads,(folder/'actions.jsonl').read_text().splitlines()):
        if e['type']=='request':requests[e['payload']['request_id']]=e
        if e['type']!='response' or not e['response'].get('accepted'):continue
        rid=e['request_id']
        if rid in accepted:continue
        accepted.add(rid);req=requests[rid];body=req['payload'];response=e['response']
        if req['path']=='/clear':
            if response['clear_result']=='success':cleared.add(body['channel']);cached.discard(body['channel'])
            continue
        if req['path']!='/measure':continue
        channel=body['channel'];point=(body['position']['x'],body['position']['y'])
        if req['phase']=='localization':
            added=[]
            for c,(s,b) in first.items():
                if c==channel or c in cleared or c in cached:continue
                q=local_offset(s,b,point);upper=range_upper(s,b,config['error_deg'])
                if not candidate(q,config['min_angle_deg'],config['error_deg']) and certified(q,upper,config['error_deg'],config['min_angle_deg']):added.append(c)
            if added:records.append(dict(primary=channel,point=point,additional_eligible_channels=sorted(added)))
        if req['phase']=='localization_shared':cached.add(channel)
        if req['phase']=='search' and response.get('measure_result')=='direction':first[channel]=(point,response['svd_deg'])
    return records


def main():
    root=Path('question3/results');result=dict(kind='OFFLINE_PUBLIC_SHARED_ELIGIBILITY_NOT_POLICY_RUN',batches={})
    for name in ['dev_main','dev_rounding','outer_main','outer_rounding']:
        folder=root/('round18_'+name);s=json.loads((folder/'summary.json').read_text());records=[]
        for row in s['cases']:
            if row['variant']=='DOMAIN':
                records += [dict(case=row['case_id'],**r) for r in inspect(folder/'DOMAIN'/row['case_id'],s['configs']['DOMAIN'])]
        result['batches'][name]=dict(decisions_with_new_opportunities=len(records),
            opportunity_count_with_repeats=sum(len(r['additional_eligible_channels']) for r in records),records=records)
    (root/'round18_shared_opportunities.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({n:{k:v for k,v in b.items() if k!='records'} for n,b in result['batches'].items()},indent=2))


if __name__=='__main__':main()
