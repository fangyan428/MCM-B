"""Explicitly invalid-feedback/deadline/retry scenarios, never performance results."""
import json
from pathlib import Path
from question3.cases import random_case
from question3.interface import Client,JsonlLog
from question3.simulator import Simulator
from question3.strategy import run


def main():
    root=Path('question3/results/round3_factorial_faults');root.mkdir(exist_ok=False)
    cfg=json.loads(Path('question3/configs/round3_factorial/ABSOD.json').read_text());rows=[]
    for fault in ['shared_no_signal','deadline_with_cached_source','shared_response_lost']:
        folder=root/fault;folder.mkdir();actions=JsonlLog(folder/'actions.jsonl');events=JsonlLog(folder/'strategy.jsonl')
        case=random_case(0);env=Simulator(case);state={'phase':None,'injected':False}
        def log(e):
            actions(e)
            if e['type']=='request':state['phase']=e['phase']
        class FaultTransport:
            def request(self,path,payload,timeout):
                status,r=env.request(path,payload,timeout)
                if state['phase']=='localization_shared' and not state['injected']:
                    if fault=='shared_no_signal':
                        state['injected']=True;r={**r,'measure_result':'no_signal'};r.pop('svd_deg',None)
                        events(dict(type='fault_injection',fault=fault))
                    elif fault=='shared_response_lost':
                        state['injected']=True;events(dict(type='fault_injection',fault=fault))
                        raise OSError('Injected loss after simulator accepted shared measurement')
                return status,r
        client=Client(FaultTransport(),'SELF',log)
        def event(e):
            events(e)
            if fault=='deadline_with_cached_source' and e['type']=='shared_cache_store' and not state['injected']:
                state['injected']=True;client.deadline=0;events(dict(type='fault_injection',fault=fault))
        result=run(client,cfg,event);expected='complete' if fault=='shared_response_lost' else 'incomplete'
        assert state['injected'] and result['status']==expected
        if expected=='incomplete':assert not result['exit_confirmed']
        else:assert result['metrics']['counts']['retries']==1 and env.evaluation()['remaining_channels']==[]
        row=dict(kind='SELF_FAULT_INJECTION_NOT_LEGAL_PERFORMANCE',fault=fault,expected=expected,result=result,evaluation=env.evaluation())
        (folder/'result.json').write_text(json.dumps(row,indent=2));(folder/'config.json').write_text(json.dumps(cfg,indent=2))
        (folder/'evaluator_hidden_case.json').write_text(json.dumps(case,indent=2));actions.close();events.close()
        rows.append(dict(fault=fault,status=result['status'],failure=result['failure']))
    (root/'summary.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))

if __name__=='__main__':main()
