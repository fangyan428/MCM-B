"""Run the locked candidate's real CLI against local self HTTP; never official."""
import json
from pathlib import Path
import subprocess
import sys
import threading
from question3.cases import random_case,clustered_case
from question3.simulator import Simulator
from question3.self_server import make_server


def main():
    root=Path('question3/results/round4_release_http');root.mkdir(exist_ok=False)
    config=Path('question3/configs/round4_holdout/ABSR1125E.json');rows=[]
    for case in [random_case(0),clustered_case()]:
        env=Simulator(case);server=make_server(env);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        out=root/case['id']
        try:
            cmd=[sys.executable,'-m','question3.run_http','--mode','self-http','--url',f'http://127.0.0.1:{server.server_port}',
                 '--config',str(config),'--output',str(out)]
            proc=subprocess.run(cmd,capture_output=True,timeout=30)
            (root/(case['id']+'_console.txt')).write_bytes(proc.stdout+proc.stderr)
            assert proc.returncode==0,proc.stderr.decode('utf-8',errors='replace')
            result=json.loads((out/'result.json').read_text(encoding='utf-8'));evaluation=env.evaluation()
            assert result['status']=='complete' and not evaluation['remaining_channels']
            assert result['config']==json.loads(config.read_text())
            if case['id']=='clustered_16':assert result['metrics']['virtual_time_s']==2431.
            (out/'post_run_evaluation.json').write_text(json.dumps(evaluation,indent=2))
            rows.append(dict(case_id=case['id'],kind='SELF_REAL_LOOPBACK_HTTP_NOT_OFFICIAL',status=result['status'],virtual_time_s=result['metrics']['virtual_time_s']))
        finally:server.shutdown();server.server_close();thread.join()
    (root/'summary.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))

if __name__=='__main__':main()
