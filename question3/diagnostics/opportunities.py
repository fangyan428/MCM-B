"""Post-run public-log diagnostics only; not new validation or strategy execution."""
import itertools
import json
import math
from pathlib import Path
import numpy as np


def enclosing_radius(vertices):
    v=np.asarray(vertices);centres=list(v)
    centres.extend((a+b)/2 for a,b in itertools.combinations(v,2))
    for a,b,c in itertools.combinations(v,3):
        A=2*np.stack([b-a,c-a]);rhs=np.array([np.dot(b-a,b-a),np.dot(c-a,c-a)])
        if abs(np.linalg.det(A))>1e-10:centres.append(a+np.linalg.solve(A,rhs))
    return min(float(np.linalg.norm(v-p,axis=1).max()) for p in centres)


def main():
    root=Path('question3/results/round2_holdout_main/AB');stats=[]
    for folder in sorted(root.iterdir()):
        events=[json.loads(x) for x in (folder/'strategy.jsonl').read_text().splitlines()]
        polygons=[e for e in events if e['type']=='localization' and 'vertices' in e]
        single=[e for e in polygons if enclosing_radius(e['vertices'])<=20-1e-7]
        pos=(0.,0.);last=None;approach=within=0.;request=None
        for line in (folder/'actions.jsonl').read_text().splitlines():
            e=json.loads(line)
            if e['type']=='request':request=e;continue
            if e['type']!='response' or not e['response'].get('accepted'):continue
            p=request['payload'].get('position')
            if p is None:continue
            new=(p['x'],p['y']);key=(request['phase'],request['payload']['channel'])
            if key[0]=='optical':
                if key==last:within+=math.dist(pos,new)/5
                else:approach+=math.dist(pos,new)/5
            pos=new;last=key
        stats.append(dict(case_id=folder.name,polygons=len(polygons),single_circle_certifiable=len(single),single_circle_but_grid_multiple=sum(e['planned_clear_calls']>1 for e in single),optical_approach_move_s=approach,optical_internal_move_s=within))
    out=dict(kind='POST_HOC_PUBLIC_LOG_DIAGNOSTIC_NOT_NEW_VALIDATION',cases=stats,
             summary={k:sum(r[k] for r in stats) for k in ['polygons','single_circle_certifiable','single_circle_but_grid_multiple']},
             mean_optical_approach_move_s=float(np.mean([r['optical_approach_move_s'] for r in stats])),
             mean_optical_internal_move_s=float(np.mean([r['optical_internal_move_s'] for r in stats])))
    target=Path('question3/results/optimization_opportunities.json');target.write_text(json.dumps(out,indent=2));print(json.dumps({k:v for k,v in out.items() if k!='cases'},indent=2))

if __name__=='__main__':main()
