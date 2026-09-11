"""Save negative-path evidence. Faults deliberately violate physics/transport contracts;
these are NOT valid benchmark cases and are excluded from clearance performance rates.
"""
import json
from pathlib import Path
from .cases import random_case
from .simulator import Simulator
from .interface import Client,JsonlLog
from .strategy import run


def main():
    config=json.loads(Path('question3/configs/baseline.json').read_text(encoding='utf-8'))
    root=Path('question3/results/fault_injection');root.mkdir(parents=True,exist_ok=True)
    summaries=[]
    for fault in ['lost_measure_response','second_point_no_signal','all_clear_feedback_failed','zero_real_budget']:
        out=root/fault;out.mkdir(exist_ok=True)
        env=Simulator(random_case(0),remaining_s=0 if fault=='zero_real_budget' else 1200)
        log=JsonlLog(out/'actions.jsonl');events=JsonlLog(out/'strategy.jsonl');phase={'localizing':False};dropped=set()
        def event(row):
            if row['type']=='coverage_complete':phase['localizing']=True
            events(row)
        class FaultTransport:
            def request(self,path,payload,timeout):
                status,r=env.request(path,payload,timeout)
                if fault=='lost_measure_response' and path=='/measure' and not dropped:
                    dropped.add(payload['request_id']);raise ConnectionError('Injected loss after accepted action')
                if fault=='second_point_no_signal' and phase['localizing'] and path=='/measure':
                    r['measure_result']='no_signal';r.pop('svd_deg',None)
                if fault=='all_clear_feedback_failed' and path=='/clear' and r.get('clear_result')=='success':
                    env._virtual_us-=2000000;env._components['laser_s']-=2;r['virtual_time_s']-=2
                    r['clear_result']='no_target_in_range'
                return status,r
        client=Client(FaultTransport(),'SELF',log,config['real_time_reserve_s'])
        result=run(client,config,event)
        expected='complete' if fault=='lost_measure_response' else 'incomplete'
        assert result['status']==expected,(fault,result)
        row=dict(kind='FAULT_INJECTION_NOT_VALID_CASE',fault=fault,expected=expected,result=result)
        (out/'result.json').write_text(json.dumps(row,indent=2),encoding='utf-8')
        summaries.append(dict(fault=fault,expected=expected,actual=result['status'],failure=result['failure']))
        log.close();events.close()
    (root/'summary.json').write_text(json.dumps(summaries,indent=2),encoding='utf-8')
    print(json.dumps(summaries,indent=2))

if __name__=='__main__':main()
