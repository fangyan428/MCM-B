"""Public first-bearing/domain range opportunities, not a candidate policy run."""
import json
import math
from pathlib import Path


def bound(position,bearing,error_deg):
    rho=math.hypot(*position)
    if rho>1800:raise ValueError('Diagnostic assumes a first point inside domain')
    if rho==0:return 1500.
    d=math.radians(error_deg);theta=math.radians(bearing)
    beta=(math.atan2(position[1],position[0])-theta+math.pi)%(2*math.pi)-math.pi
    cosine=-1. if abs(beta)+d>=math.pi else min(math.cos(beta-d),math.cos(beta+d))
    projection=rho*cosine
    return min(1500.,-projection+math.sqrt(projection**2+1800**2-rho**2))


def main():
    root=Path('question3/results');report=dict(kind='OFFLINE_PUBLIC_RANGE_OPPORTUNITY_NOT_POLICY_BENEFIT',batches={})
    for name in ['dev_main','dev_rounding','adverse_main','adverse_rounding']:
        folder=root/('round17_'+name);summary=json.loads((folder/'summary.json').read_text());rows=[]
        for row in summary['cases']:
            if row['variant']!='REF':continue
            f=folder/'REF'/row['case_id'];requests={};found=set()
            for e in map(json.loads,(f/'actions.jsonl').read_text().splitlines()):
                if e['type']=='request':requests[e['payload']['request_id']]=e
                if e['type']!='response' or not e['response'].get('accepted'):continue
                q=requests[e['request_id']];res=e['response']
                if q['path']!='/measure' or res.get('measure_result')!='direction':continue
                p=q['payload'];c=p['channel']
                if c in found:continue
                found.add(c);position=(p['position']['x'],p['position']['y']);bearing=res['svd_deg']
                upper=bound(position,bearing,summary['configs']['REF']['error_deg'])
                rows.append(dict(case=row['case_id'],channel=c,first=position,bearing=bearing,public_range_upper_m=upper))
        report['batches'][name]=dict(first_direction_count=len(rows),below_1500=sum(r['public_range_upper_m']<1500-1e-7 for r in rows),
            at_most_1000=sum(r['public_range_upper_m']<=1000 for r in rows),records=rows)
    (root/'round17_public_range_opportunities.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({n:{k:v for k,v in b.items() if k!='records'} for n,b in report['batches'].items()},indent=2))


if __name__=='__main__':main()
