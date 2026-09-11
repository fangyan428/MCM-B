"""Exercise P through the real CLI and local self HTTP; not official."""
import json
from pathlib import Path
import subprocess
import sys
import threading
from question3.cases import random_case
from question3.simulator import Simulator
from question3.self_server import make_server


def main():
    root=Path('question3/results/round14_self_http');root.mkdir(exist_ok=False);rows=[]
    for name in ['PHASE']:
        env=Simulator(random_case(0));server=make_server(env)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        out=root/name;config=Path('question3/configs/round14_dev',name+'.json')
        try:
            p=subprocess.run([sys.executable,'-m','question3.run_http','--mode','self-http',
                '--url',f'http://127.0.0.1:{server.server_port}','--config',str(config),'--output',str(out)],
                capture_output=True,timeout=30)
            (root/(name+'_console.txt')).write_bytes(p.stdout+p.stderr)
            assert p.returncode==0,p.stderr.decode('utf-8',errors='replace')
            result=json.loads((out/'result.json').read_text());truth=env.evaluation()
            assert result['status']=='complete' and not truth['remaining_channels']
            es=list(map(json.loads,(out/'strategy.jsonl').read_text().splitlines()))
            count=sum(e['type']=='ring_phase_selected' and abs(e['phase_rad'])>1e-9 for e in es)
            assert count>0
            (out/'post_run_evaluation.json').write_text(json.dumps(truth,indent=2)+'\n')
            rows.append(dict(variant=name,kind='SELF_REAL_LOOPBACK_HTTP_NOT_OFFICIAL',complete=True,
                actual_phase_changes=count,virtual_time_s=result['metrics']['virtual_time_s']))
        finally:server.shutdown();server.server_close();thread.join()
    (root/'summary.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows,indent=2))


if __name__=='__main__':main()
