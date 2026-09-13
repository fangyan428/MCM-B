"""Independent candidate entry using the repository's existing official HTTP client.

Only self HTTP or a human-opened Q3 rehearsal; never starts the simulator.
The original question3.run_http entry and recommended configuration are unchanged.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path
from .interface import Client, HttpTransport, JsonlLog
from .innovation.strategy import run


class PublicClient:
    """Expose only public action/observation capabilities to the candidate."""
    __slots__ = ('__client',)

    def __init__(self, client): self.__client = client
    @property
    def position(self): return self.__client.position
    @property
    def channel(self): return self.__client.channel
    def enter(self): return self.__client.enter()
    def measure(self, *args, **kwargs): return self.__client.measure(*args, **kwargs)
    def clear(self, *args, **kwargs): return self.__client.clear(*args, **kwargs)
    def exit(self): return self.__client.exit()
    def metrics(self): return self.__client.metrics()


def main():
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['self-http', 'official-rehearsal'], default='self-http')
    parser.add_argument('--url')
    parser.add_argument('--robot-id', default='SELF')
    parser.add_argument('--confirm-rehearsal-ui', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.mode == 'official-rehearsal' and (not args.confirm_rehearsal_ui or args.robot_id == 'SELF'):
        parser.error('Confirm official Q3 REHEARSAL UI and supply team robot-id. Formal mode is not implemented.')
    config = json.loads((root / 'innovation/best_candidate.json').read_text(encoding='utf-8'))
    url = args.url or ('http://127.0.0.1:2027' if args.mode == 'self-http' else 'http://127.0.0.1:2026')
    args.output.mkdir(parents=True, exist_ok=False)

    def save(name, value):
        (args.output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

    save('config.json', config)
    files = [Path(__file__), root / 'interface.py', root / 'geometry.py', root / 'modules.py']
    files += sorted((root / 'innovation').glob('*.py'))
    save('code_sha256.json', {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    log = JsonlLog(args.output / 'actions.jsonl')
    events = JsonlLog(args.output / 'strategy.jsonl')
    client = Client(HttpTransport(url), args.robot_id, log, config['baseline_config']['real_time_reserve_s'])
    start = time.perf_counter()
    try:
        try:
            result = run(PublicClient(client), config, events)
        except Exception as exc:
            result = dict(status='incomplete', failure=f'{type(exc).__name__}: {exc}', metrics=client.metrics())
        result.update(kind=args.mode, config=config, elapsed_wall_s=time.perf_counter() - start,
                      official_total=None, clearance_ratio=None,
                      note='Official count must be read from rehearsal UI after exit; no hidden count in HTTP API.')
        save('result.json', result)
    finally:
        log.close()
        events.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result['status'] != 'complete':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
