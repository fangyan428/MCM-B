"""Public AB trajectory opportunity count, not a counterfactual time experiment."""
import json
import math
from pathlib import Path
from question2.strategy import candidate


def main():
    rows=[]
    for folder in sorted(Path('question3/results/round2_holdout_main/AB').iterdir()):
        first={};cleared=set();req=None;total=eligible=matches=0
        for line in (folder/'actions.jsonl').read_text().splitlines():
            e=json.loads(line)
            if e['type']=='request':
                req=e
                if e['path']=='/measure' and e['phase']=='localization':
                    total+=1;p=e['payload']['position'];c=e['payload']['channel'];count=0
                    for other,(pos,bearing) in first.items():
                        if other==c or other in cleared:continue
                        a=math.radians(bearing);dx=p['x']-pos['x'];dy=p['y']-pos['y']
                        q=[dx*math.cos(a)+dy*math.sin(a),-dx*math.sin(a)+dy*math.cos(a)]
                        if candidate(q,20,1.005):count+=1
                    eligible+=bool(count);matches+=count
                continue
            if e['type']!='response' or not e['response'].get('accepted'):continue
            r=e['response'];p=req['payload'];c=p.get('channel')
            if req['path']=='/measure' and r.get('measure_result')=='direction':first.setdefault(c,(p['position'],r['svd_deg']))
            if req['path']=='/clear' and r.get('clear_result')=='success':cleared.add(c)
        rows.append(dict(case_id=folder.name,second_measurements=total,points_compatible_with_other_pending=eligible,compatible_other_channels=matches))
    data=dict(kind='POST_HOC_PUBLIC_LOG_OPPORTUNITY_NOT_PERFORMANCE_VALIDATION',cases=rows,
              totals={k:sum(r[k] for r in rows) for k in ['second_measurements','points_compatible_with_other_pending','compatible_other_channels']})
    Path('question3/results/shared_point_opportunities.json').write_text(json.dumps(data,indent=2));print(data['totals'])

if __name__=='__main__':main()
