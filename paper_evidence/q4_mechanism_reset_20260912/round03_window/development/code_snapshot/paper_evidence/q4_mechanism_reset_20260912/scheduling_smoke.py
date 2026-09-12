"""SELF regression checks on historical seed range; not performance selection.

Run from repository root with python -m
paper_evidence.q4_mechanism_reset_20260912.scheduling_smoke. Assertions concern
completion, physical accounting and identity ablation, not candidate ranking.
"""
import json
from pathlib import Path

from question3.interface import Client
from question4.audit import audit
from question4.cases import make_case
from question4.simulator import Simulator
from question4.strategy import run as baseline
from question4.innovation.experiment import PublicClient
from question4.innovation.strategy import BASELINE_CONFIG, run as adapt_run
from .scheduling import CANDIDATES, run


def execute(case, runner, config):
    records = []
    client = Client(Simulator(case), 'SELF', records.append)
    result = runner(PublicClient(client), config)
    checked = audit(case, records, result)
    signature = []
    for record in records:
        if record['type'] == 'request':
            payload = record['payload']
            signature.append((record['path'], payload.get('position'), payload.get('channel'), record['phase']))
    return result, signature, checked


def main():
    rows = []
    families = ('uniform', 'outward', 'inward', 'tangent', 'cluster', 'edge')
    for index, family in enumerate(families):
        case = make_case(71000+index, family, 'spatial_hash')
        for name, config in CANDIDATES.items():
            result, _, checked = execute(case, run, config)
            assert checked['passed'] and result['status'] == 'complete'
            rows.append(dict(case=case['id'], candidate=name, check='complete_physical_audit', passed=True))
    case = make_case(71000, 'uniform', 'spatial_hash')
    for parent, original, original_config in (
        ('baseline', baseline, BASELINE_CONFIG),
        ('adapt', adapt_run, {'mechanism': 'parallax', 'sharing': 'gated'}),
    ):
        a, signature_a, _ = execute(case, original, original_config)
        b, signature_b, _ = execute(case, run, {'schedule': 'baseline', 'schedule_parent': parent})
        assert a == b and signature_a == signature_b
        rows.append(dict(check='parent_ablation_action_and_result_identity', parent=parent, passed=True))
    output = Path(__file__).with_name('scheduling_smoke.json')
    output.write_text(json.dumps(dict(stage='historical_self_regression_not_selection',
        cases_note='Six historical seed-range layouts, one fixed spatial error field, bounded rounding.',
        performance_used_for_selection=False, checks=rows), indent=2)+'\n')
    print(json.dumps(dict(passed=len(rows), failed=0, output=str(output))))


if __name__ == '__main__':
    main()
