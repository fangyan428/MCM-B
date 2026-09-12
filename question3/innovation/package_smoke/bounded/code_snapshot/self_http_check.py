"""Actual localhost self HTTP check; bind an OS-assigned port, never port 2026."""
import json
import threading
from .experiment import ROOT,PublicClient,dump
from .strategy import run
from question3.simulator import Simulator
from question3.cases import random_case,clustered_case
from question3.interface import Client,HttpTransport,JsonlLog
from question3.self_server import make_server
from question3.audit import audit_folder
from .experiment import audit_new

def main():
    config=json.loads((ROOT/'best_candidate.json').read_text())
    rows=[]
    for case in [random_case(0),clustered_case()]:
        folder=ROOT/'self_http'/case['id'];folder.mkdir(parents=True,exist_ok=False)
        env=Simulator(case);server=make_server(env,0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        log=JsonlLog(folder/'actions.jsonl');events=JsonlLog(folder/'strategy.jsonl')
        try:
            assert server.server_port!=2026
            client=Client(HttpTransport(f'http://127.0.0.1:{server.server_port}'),'SELF',log)
            result=run(PublicClient(client),config,events)
        finally:
            server.shutdown();server.server_close();thread.join();log.close();events.close()
        truth=env.evaluation();assert result['status']=='complete' and not truth['remaining_channels']
        dump(folder/'evaluator_hidden_case.json',case)
        summary=dict(case_id=case['id'],rounding='bounded',status=result['status'],virtual_time_s=truth['virtual_time_s'],
                     total=truth['total'],cleared=truth['cleared'],self_port=server.server_port,official_runs=0)
        dump(folder/'result.json',dict(summary=summary,strategy=result))
        summary['audited_actions']=audit_folder(folder);summary['events']=audit_new(folder);rows.append(summary)
    dump(ROOT/'self_http_check.json',rows);print(json.dumps(rows,indent=2))

if __name__=='__main__':main()
