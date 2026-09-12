"""Reproduce selected SELF actions from public response logs without a simulator."""
import json
from pathlib import Path
from question3.interface import Client
from question4.innovation.experiment import PublicClient
from question4.innovation.strategy import run

ROOT = Path('question4/innovation')


class Replay:
    def __init__(self, rows):
        self.calls = [r for r in rows if r['type'] == 'request' and r.get('attempt', 0) == 0]
        self.responses = {r['request_id']: r for r in rows if r['type'] == 'response'}
        self.index = 0

    def request(self, path, payload, timeout=5.):
        expected = self.calls[self.index]
        self.index += 1
        assert path == expected['path']
        assert {k: v for k, v in payload.items() if k != 'request_id'} == {
            k: v for k, v in expected['payload'].items() if k != 'request_id'}
        response = self.responses[expected['payload']['request_id']]
        return response['http_status'], response['response'].copy()


def main():
    batch = ROOT/'results/final_validation'
    rows = json.loads((batch/'summary.json').read_text())['rows']
    candidate = 'ADAPT_GATED'
    selected = [r for r in rows if r['config'] == candidate and r['rounding'] == 'bounded']
    baseline = {r['case_id']: r for r in rows if r['config'] == 'BASE'}
    worst = max(selected, key=lambda r: r['metrics']['virtual_time_s']/baseline[r['case_id']]['metrics']['virtual_time_s'])
    maximum = max(selected, key=lambda r: r['metrics']['virtual_time_s'])
    difficult = max(selected, key=lambda r: r['event_counts'].get('adaptive_attempt', 0))
    config = json.loads((ROOT/'best_candidate.json').read_text())
    results = []
    for source in {r['case_id']: r for r in [worst, maximum, difficult]}.values():
        folder = batch/candidate/source['case_id']
        transport = Replay([json.loads(line) for line in (folder/'actions.jsonl').read_text().splitlines()])
        client = Client(transport, 'SELF')
        result = run(PublicClient(client), config)
        assert result['metrics'] == source['metrics']
        assert transport.index == len(transport.calls)
        results.append(dict(case_id=source['case_id'], actions=transport.index,
                            metrics_equal=True, source_truth_or_simulator_provided=False))
    (ROOT/'public_replay.json').write_text(json.dumps(results, indent=2)+'\n')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
