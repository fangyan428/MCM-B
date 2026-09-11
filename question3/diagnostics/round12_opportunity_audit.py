"""Reconstruct complete optical plans from public observations, not hidden cases.
Unexecuted plan points are only geometric opportunities, never measured outcomes.
"""
import json
import math
from pathlib import Path
import numpy as np
from question3.clear_skip import constraints,failure_certificate


def main():
    report=dict(kind='SELF_ROUND12_PUBLIC_GEOMETRY_OPPORTUNITY_AUDIT',batches={})
    for suffix in ['dev_main','dev_rounding','adverse_main','adverse_rounding']:
        root=Path('question3/results')/('round12_'+suffix)
        summary=json.loads((root/'summary.json').read_text());cfg=summary['configs']['REF']
        total=single=extra=regions=0
        for row in summary['cases']:
            if row['variant']!='REF':continue
            folder=root/'REF'/row['case_id'];requests={};bearings={}
            for e in map(json.loads,(folder/'actions.jsonl').read_text().splitlines()):
                if e['type']=='request':requests[e['payload']['request_id']]=e['payload']
                if e['type']=='response' and e['response'].get('measure_result')=='direction':
                    q=requests[e['request_id']];bearings[q['position']['x'],q['position']['y'],q['channel']]=e['response']['svd_deg']
            for e in map(json.loads,(folder/'strategy.jsonl').read_text().splitlines()):
                if e['type']!='localization' or 'vertices' not in e:continue
                regions+=1;first=e['first_position'];second=e['second_position'];c=e['channel']
                theta=bearings[(*first,c)];reading=bearings[(*second,c)]
                planes=constraints(first,theta,second,reading,cfg['error_deg'])
                angle=math.radians(theta);R=np.array([[math.cos(angle),-math.sin(angle)],[math.sin(angle),math.cos(angle)]])
                local=(np.array(e['vertices'])-first)@R;lo=local.min(axis=0)-1e-5;hi=local.max(axis=0)+1e-5
                size=np.maximum(1,np.ceil((hi-lo)/cfg['optical_cell_m']).astype(int))
                assert int(np.prod(size))==e['planned_clear_calls']
                for i in range(size[0]):
                    for j in range(size[1]):
                        p=np.array(first)+R@(lo+(np.array([i+.5,j+.5])/size)*(hi-lo));total+=1
                        if failure_certificate(p,planes):single+=1
                        elif failure_certificate(p,planes,combine=True):extra+=1
        report['batches'][suffix]=dict(regions=regions,all_planned_points=total,
            single_halfplane_possible_skips=single,pair_additional_possible_skips=extra)
    Path('question3/results/round12_opportunities.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
