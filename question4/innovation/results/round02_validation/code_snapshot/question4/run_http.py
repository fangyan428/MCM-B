"""Connect to self HTTP or an already-ready official Q4 rehearsal."""
import argparse
import json
import time
from pathlib import Path
from question3.interface import Client, HttpTransport, JsonlLog
from .strategy import run

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--mode',choices=['self-http','official-rehearsal'],default='self-http')
    p.add_argument('--url');p.add_argument('--robot-id',default='SELF')
    p.add_argument('--confirm-rehearsal-ui',action='store_true',help='Operator confirms Q4 rehearsal UI is ready')
    p.add_argument('--output',required=True)
    p.add_argument('--config',type=Path,default=Path(__file__).with_name('configs')/'recommended.json')
    args=p.parse_args()
    if args.mode=='official-rehearsal' and (not args.confirm_rehearsal_ui or args.robot_id=='SELF'):
        p.error('Confirm official Q4 rehearsal UI and supply the logged-in team robot-id.')
    config=json.loads(args.config.read_text(encoding='utf-8'))
    out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    (out/'config.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
    actions=JsonlLog(out/'actions.jsonl');events=JsonlLog(out/'strategy.jsonl')
    url=args.url or ('http://127.0.0.1:2028' if args.mode=='self-http' else 'http://127.0.0.1:2026')
    client=Client(HttpTransport(url),args.robot_id,actions)
    start=time.perf_counter()
    try:
        result=run(client,config,events)
    except Exception as exc:
        result=dict(status='incomplete',failure=f'{type(exc).__name__}: {exc}',metrics=client.metrics())
    finally:
        actions.close();events.close()
    result.update(mode=args.mode,elapsed_wall_s=time.perf_counter()-start,official_total=None,
                  official_clearance_ratio=None,config=config)
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='stop_certificate'},ensure_ascii=False,indent=2))
    if result['status']!='complete':raise SystemExit(1)

if __name__=='__main__':main()
