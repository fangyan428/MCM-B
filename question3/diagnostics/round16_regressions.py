"""Post-run only: preserve every regression and inspect representative task sequences."""
import json
from pathlib import Path


def main():
    root=Path('question3/results');evidence=json.loads((root/'round16_review_evidence.json').read_text())
    report=dict(kind='POST_RUN_DIAGNOSTIC_NOT_NEW_VALIDATION',batches={},representatives=[])
    for name in evidence['batches']:
        folder=root/('round16_'+name);rows=json.loads((folder/'summary.json').read_text())['cases']
        by={(r['variant'],r['case_id']):r for r in rows};regressions=[]
        for i in sorted({r['case_id'] for r in rows}):
            a,b=by['REF',i],by['FREE',i];ta=a['metrics']['virtual_time_s'];tb=b['metrics']['virtual_time_s']
            if tb>ta+1e-7:
                regressions.append(dict(case=i,ref_s=ta,free_s=tb,delta_s=tb-ta,increase_pct=100*(tb/ta-1),
                    components_delta_s={k:b['metrics']['components'][k]-a['metrics']['components'][k] for k in a['metrics']['components']}))
        report['batches'][name]=sorted(regressions,key=lambda r:r['increase_pct'],reverse=True)
    for name,i in [('holdout_main','holdout_210032_positive'),('holdout_main','holdout_210044_smooth'),
                   ('adverse_main','holdout_130023_smooth'),('adverse_main','outer_holdout_120008_spatial_hash')]:
        sequences={}
        for v in ['REF','FREE']:
            f=root/('round16_'+name)/v/i
            es=list(map(json.loads,(f/'strategy.jsonl').read_text().splitlines()))
            sequences[v]=[dict(task=e['task'],id=e.get('channel',e.get('station_id')),forced=e.get('forced',False)) for e in es if e['type']=='schedule']
        j=next((j for j,(a,b) in enumerate(zip(sequences['REF'],sequences['FREE'])) if (a['task'],a['id'])!=(b['task'],b['id'])),None)
        report['representatives'].append(dict(batch=name,case=i,first_different_task_zero_based=j,sequences=sequences))
    out=root/'round16_all_regressions.json';out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:len(v) for k,v in report['batches'].items()},indent=2))


if __name__=='__main__':main()
