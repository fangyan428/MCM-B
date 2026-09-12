"""SELF-only bounded mechanism smoke and continuous-certificate regression checks."""
import copy
import json
from pathlib import Path
import numpy as np
from paper_evidence.q4_mechanism_reset_20260912.coverage import run,CANDIDATES,triangle_certificate,cell_certificate
from question4.geometry import radial_mesh
from question4.cases import fixtures
from question4.simulator import Simulator
from question3.interface import Client
from question4.audit import audit,check_cover

ROOT=Path(__file__).parent

def main():
    p,_=radial_mesh();assert triangle_certificate(p) is not None
    assert cell_certificate(p) is not None
    for i in (0,1,13):
        assert triangle_certificate(np.delete(p,i,axis=0)) is None
        assert cell_certificate(np.delete(p,i,axis=0)) is None
    assert triangle_certificate(np.array([[1800,0],[1800,0],[1800,0]])) is None
    proof=cell_certificate(p);check_cover(json.dumps(proof))
    bad=copy.deepcopy(proof);bad['leaves'].pop()
    try:check_cover(json.dumps(bad))
    except AssertionError:pass
    else:raise AssertionError('Missing cell accepted')
    rows=[]
    for case in fixtures(918200,6):
        for name,config in CANDIDATES.items():
            records=[];events=[];env=Simulator(case);client=Client(env,'SELF',records.append)
            result=run(client,config,events.append);truth=env.evaluation()
            assert truth['total']==truth['cleared']
            cert=result['stop_certificate']
            if cert['kind']=='dynamic_cell_halfplane_cover':
                # Root evaluator additionally performs full physical replay.
                assert np.array_equal(check_cover(json.dumps(cert['dynamic_cover'])),cert['stations'])
                requests={r['payload']['request_id']:r for r in records if r['type']=='request'}
                measured={ch:set() for ch in range(1,21)}
                for r in records:
                    if r['type']=='response' and r['path']=='/measure':
                        b=requests[r['request_id']]['payload'];measured[b['channel']].add((b['position']['x'],b['position']['y']))
                for ch in set(range(1,21))-set(result['cleared']):
                    assert all(tuple(q) in measured[ch] for q in cert['stations'])
            else:audit(case,records,result)
            row=dict(case=case['id'],name=name,time_s=client.virtual,cleared=truth['cleared'],
                     certificate=cert['kind'],exchanges=sum(e['event']=='coverage_exchange' for e in events),
                     elastic=sum(e['event']=='coverage_elastic' for e in events),status='complete')
            rows.append(row);print(row,flush=True)
    (ROOT/'coverage_smoke.json').write_text(json.dumps({'geometry_checks':'passed','rows':rows},indent=2))

if __name__=='__main__':main()
