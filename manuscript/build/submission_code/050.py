"""Replay public Q4 request/response logs without importing an evaluator.

python -m paper_evidence.q4_mechanism_reset_20260912.qa.replay \
  --case-dir path/to/batch/CANDIDATE/case_id \
  --config path/to/configs.json --config-name CANDIDATE \
  --output path/to/new_replay_directory

--config also accepts an inline JSON policy object. Outputs must not exist.
The policy receives public action methods only, backed by recorded responses;
no Simulator, fixture, source table, hidden-case file, or true count is loaded.
"""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import traceback

from question3.interface import Client

PROJECT = Path(__file__).resolve().parents[3]
ENTRY_MODULE = 'paper_evidence.q4_mechanism_reset_20260912.strategy'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as out:
        json.dump(value, out, ensure_ascii=False, indent=2, allow_nan=False)
        out.write('\n')


class PublicActions:
    """Capability wrapper. No transport or evaluator attribute is exposed."""
    __slots__ = ('__delegate',)

    def __init__(self, delegate):
        self.__delegate = delegate

    @property
    def position(self):
        return self.__delegate.position

    @property
    def channel(self):
        return self.__delegate.channel

    def enter(self):
        return self.__delegate.enter()

    def measure(self, *args, **kwargs):
        return self.__delegate.measure(*args, **kwargs)

    def clear(self, *args, **kwargs):
        return self.__delegate.clear(*args, **kwargs)

    def exit(self):
        return self.__delegate.exit()

    def metrics(self):
        return self.__delegate.metrics()


def signature(path, payload):
    # Request identifiers are per-process idempotency tokens, not policy input.
    return path, {k: v for k, v in payload.items() if k != 'request_id'}


class RecordedResponses:
    """Strict sequential transport containing only a public transcript.

    A response becomes available only after its preceding request matches
    exactly, including all point coordinates and channel. Retry outcomes are
    retained; an exhausted retry remains a replay failure rather than success.
    """
    __slots__ = ('__steps', '__cursor', '__id_map')

    def __init__(self, rows):
        steps = []
        pending = None
        for row in rows:
            kind = row.get('type')
            if kind == 'request':
                if pending is not None:
                    raise ValueError('Transcript has a request with no outcome')
                pending = copy.deepcopy(row)
            elif kind in ('response', 'transport_error'):
                if pending is None or row['request_id'] != pending['payload']['request_id']:
                    raise ValueError('Transcript outcome does not match its preceding request')
                steps.append((pending, copy.deepcopy(row)))
                pending = None
        if pending is not None or not steps:
            raise ValueError('Transcript is empty or ends with an unresolved request')
        self.__steps = steps
        self.__cursor = 0
        self.__id_map = {}

    @property
    def progress(self):
        return self.__cursor, len(self.__steps)

    def request(self, path, payload, timeout=5.):
        if self.__cursor >= len(self.__steps):
            raise AssertionError('Policy emitted an extra action after the recorded transcript')
        expected, outcome = self.__steps[self.__cursor]
        action_index = self.__cursor
        if signature(path, payload) != signature(expected['path'], expected['payload']):
            raise AssertionError('Public action mismatch at index '+str(action_index)+': '+
                                 json.dumps({'expected': signature(expected['path'], expected['payload']),
                                             'actual': signature(path, payload)}, ensure_ascii=False))
        old_id, new_id = expected['payload']['request_id'], payload['request_id']
        if old_id in self.__id_map and self.__id_map[old_id] != new_id:
            raise AssertionError('A replayed retry changed its request identifier')
        if old_id not in self.__id_map and new_id in self.__id_map.values():
            raise AssertionError('Distinct actions reused a replay request identifier')
        self.__id_map[old_id] = new_id
        self.__cursor += 1
        if outcome['type'] == 'transport_error':
            raise OSError(outcome.get('error', 'Recorded transport error'))
        # Timestamp is retained, but never used to derive positions or truth.
        return outcome['http_status'], copy.deepcopy(outcome['response'])


def _module_path(module, project):
    path = project.joinpath(*module.split('.'))
    if path.with_suffix('.py').is_file():
        return path.with_suffix('.py')
    if (path/'__init__.py').is_file():
        return path/'__init__.py'
    return None


def static_scan(entry=ENTRY_MODULE, project=PROJECT):
    """AST dependency scan; useful evidence, explicitly not a sandbox proof."""
    project = Path(project)
    forbidden_module_parts = {'simulator', 'cases', 'experiment', 'self_server', 'run_http'}
    forbidden_attributes = {'transport', 'Simulator', 'evaluation', '_sources', '_seed',
                            '_error_mode', '_rounding', 'case', 'hidden', 'truth',
                            'evaluator_hidden_case', 'direction_deg'}
    forbidden_keys = {'sources', 'seed', 'direction_deg', 'evaluator_hidden_case',
                      'hidden_case', '_sources', '_seed'}
    dynamic_calls = {'eval', 'exec', '__import__', 'getattr', 'setattr', 'globals', 'locals', 'vars'}
    seen = set(); queue = [entry]; modules = []; violations = []; reviews = []
    while queue:
        module = queue.pop()
        if module in seen:
            continue
        seen.add(module)
        path = _module_path(module, project)
        if path is None:
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        imports = []
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Import):
                targets = [x.name for x in node.names]
            elif isinstance(node, ast.ImportFrom):
                package = module if path.name == '__init__.py' else module.rsplit('.',1)[0]
                target = importlib.util.resolve_name('.'*node.level+(node.module or ''), package) if node.level else (node.module or '')
                targets = [target]
            for target in targets:
                imports.append(target)
                if forbidden_module_parts.intersection(target.split('.')):
                    violations.append({'module':module,'line':node.lineno,'kind':'forbidden_import','value':target})
                if _module_path(target, project) is not None:
                    queue.append(target)
            if isinstance(node, ast.Attribute) and node.attr in forbidden_attributes:
                violations.append({'module':module,'line':node.lineno,'kind':'forbidden_attribute','value':node.attr})
            if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load):
                key = node.slice.value if isinstance(node.slice, ast.Constant) else None
                if isinstance(key, str) and key in forbidden_keys:
                    violations.append({'module':module,'line':node.lineno,'kind':'forbidden_key','value':key})
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func,ast.Name) else node.func.attr if isinstance(node.func,ast.Attribute) else None
                if name in dynamic_calls:
                    reviews.append({'module':module,'line':node.lineno,'kind':'dynamic_introspection_review','value':name})
                if name in {'open','read_text','read_bytes','load','loads'}:
                    reviews.append({'module':module,'line':node.lineno,'kind':'file_or_decoder_review','value':name})
        modules.append({'module':module,'path':str(path.relative_to(project)),
                        'sha256':digest(path),'imports':sorted(set(imports))})
    return {'entry':entry,'passed':not violations,'modules':sorted(modules,key=lambda row:row['module']),
            'violations':violations,'manual_review_findings':reviews,
            'scope':'Recursively follows repository Python imports from policy dispatcher; external libraries are not analyzed.',
            'limitation':'AST checks are evidence of inspected code and do not prove absence of arbitrary dynamic behavior or constitute a security sandbox.'}


def load_config(value, name=None):
    config = json.loads(value) if value.lstrip().startswith('{') else json.loads(Path(value).read_text(encoding='utf-8'))
    if name is not None:
        config = config[name]
    if not isinstance(config, dict) or 'family' not in config:
        raise ValueError('Expected one dispatcher policy configuration; select a matrix arm with --config-name')
    return config


def replay(case_dir, config, output):
    case_dir, output = Path(case_dir).resolve(), Path(output).resolve()
    if output == case_dir or case_dir in output.parents:
        raise ValueError('Replay output must be outside the source case directory')
    output.mkdir(parents=True, exist_ok=False)
    records = [json.loads(line) for line in (case_dir/'actions.jsonl').read_text(encoding='utf-8').splitlines() if line]
    # The result is evaluator-owned comparison material and never reaches the
    # public transport or policy. In particular, evaluator_hidden_case is unread.
    document = json.loads((case_dir/'result.json').read_text(encoding='utf-8'))
    expected = document.get('strategy', document)
    transport = RecordedResponses(records)
    robot_ids = {r['payload']['robot_id'] for r in records if r.get('type') == 'request'}
    if len(robot_ids) != 1:
        raise ValueError('A replay transcript must belong to one robot ID')
    produced, events = [], []
    client = Client(transport, robot_ids.pop(), produced.append)
    public = PublicActions(client)
    assert not any(hasattr(public, name) for name in ('transport','Simulator','hidden','case','truth','evaluation'))
    scan = static_scan()
    write_new(output/'static_scan.json', scan)
    report = {'source_directory':str(case_dir),'source_actions_sha256':digest(case_dir/'actions.jsonl'),
              'source_result_sha256':digest(case_dir/'result.json'),'config':config,
              'source_truth_or_simulator_provided':False,'hidden_case_file_read':False,
              'static_scan_passed':scan['passed'],'passed':False}
    try:
        if not scan['passed']:
            raise AssertionError('Policy dependency scan found forbidden evaluator access')
        from paper_evidence.q4_mechanism_reset_20260912.strategy import run
        result = run(public, copy.deepcopy(config), events.append)
        cursor, total = transport.progress
        assert cursor == total, 'Policy stopped before all recorded actions were consumed'
        assert result['status'] == expected['status'], 'Completion status differs'
        assert result.get('cleared') == expected.get('cleared'), 'Cleared channel list differs'
        assert result['metrics'] == expected['metrics'], 'Full public time accounting differs'
        assert result.get('stop_certificate') == expected.get('stop_certificate'), 'Stop certificate differs'
        original_phases = [r.get('phase') for r in records if r.get('type') == 'request']
        replay_phases = [r.get('phase') for r in produced if r.get('type') == 'request']
        assert replay_phases == original_phases, 'Action phase attribution differs'
        report.update(passed=True,actions=cursor,all_positions_channels_exact=True,
                      cleared_equal=True,metrics_equal=True,stop_certificate_equal=True,phases_equal=True)
        write_new(output/'result.json',result)
    except Exception as exc:
        report.update(failure=f'{type(exc).__name__}: {exc}',traceback=traceback.format_exc(),
                      consumed_actions=transport.progress[0],recorded_actions=transport.progress[1])
    for filename, rows in (('actions.jsonl', produced), ('strategy.jsonl', events)):
        with (output/filename).open('x',encoding='utf-8') as handle:
            for row in rows:
                handle.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
    write_new(output/'replay.json',report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--case-dir',required=True)
    parser.add_argument('--config',required=True,help='Single policy JSON path or inline JSON; matrices require --config-name')
    parser.add_argument('--config-name')
    parser.add_argument('--output',required=True,help='New output directory outside source case folder')
    args=parser.parse_args()
    report=replay(args.case_dir,load_config(args.config,args.config_name),args.output)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
