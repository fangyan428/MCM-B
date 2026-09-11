"""Run strategy against self HTTP or an already-open official Q3 REHEARSAL.
No formal-test mode; no simulator UI automation; no exe launch.
"""
import argparse
import json
import time
from pathlib import Path
from .interface import Client,HttpTransport,JsonlLog
from .strategy import run


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--mode',choices=['self-http','official-rehearsal'],default='self-http')
    p.add_argument('--url');p.add_argument('--robot-id',default='SELF')
    p.add_argument('--confirm-rehearsal-ui',action='store_true',help='Human confirms Q3 rehearsal, NOT formal UI')
    p.add_argument('--output',required=True)
    args=p.parse_args()
    if args.mode=='official-rehearsal' and (not args.confirm_rehearsal_ui or args.robot_id=='SELF'):
        p.error('Confirm official Q3 REHEARSAL UI and supply team robot-id. Formal mode is not implemented.')
    url=args.url or ('http://127.0.0.1:2027' if args.mode=='self-http' else 'http://127.0.0.1:2026')
    out=Path(args.output)
    out.mkdir(parents=True,exist_ok=False)
    config=json.loads(Path(__file__).with_name('configs').joinpath('baseline.json').read_text())
    log=JsonlLog(out/'actions.jsonl');events=JsonlLog(out/'strategy.jsonl')
    client=Client(HttpTransport(url),args.robot_id,log,config['real_time_reserve_s'])
    start=time.perf_counter()
    try:result=run(client,config,events)
    except Exception as e:result=dict(status='incomplete',failure=f'{type(e).__name__}: {e}',metrics=client.metrics())
    result.update(kind=args.mode,config=config,elapsed_wall_s=time.perf_counter()-start,
                  official_total=None,clearance_ratio=None,
                  note='Official count must be read from rehearsal UI after exit; no hidden count in HTTP API.')
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    log.close();events.close();print(json.dumps(result,ensure_ascii=False,indent=2))
    if result['status']!='complete':raise SystemExit(1)

if __name__=='__main__':main()
