"""Exercise v1 migration and code reuse with an installed Reporter wheel.

The server is a local fixture. Backend authentication and result certification
are covered separately by ShopOps backend tests.
"""

import copy
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

import yaml

from shopops_reporter import __version__, cli
from shopops_reporter.config import ProjectConfig
from shopops_reporter.daemon import Uploader
from shopops_reporter.project import project_fingerprint
from shopops_reporter.result_mapping.loader import canonical_digest, load_result_contract
from shopops_reporter.result_mapping.policy import CONTRACT_V2, reporting_policy
from shopops_reporter.runner import run_project
from shopops_reporter.spool import Spool
from shopops_reporter.task_context import TaskContext


class FixtureServer:
    def __init__(self):
        self.contracts = {}
        self.calls = []
        self.fail_submission = False

    def signed_get(self, path):
        assert path == '/reporter/v1/capabilities'
        return {'result_contract_schemas': [CONTRACT_V2]}

    def signed_json(self, method, path, body):
        assert method == 'POST'
        self.calls.append((path, copy.deepcopy(body)))
        if path.endswith('/result-contracts'):
            if self.fail_submission:
                raise ConnectionError('synthetic offline submission')
            digest = body['digest']
            created = digest not in self.contracts
            if created:
                self.contracts[digest] = {
                    'id': 'fixture-v2', 'version': 2, 'digest': digest, 'status': 'pending',
                }
            return {**self.contracts[digest], 'created': created}
        if path.endswith('/start'):
            return {'run_id': body['external_run_key']}
        if path.endswith('/logs:batch'):
            return {'last_log_sequence': body['records'][-1]['sequence']}
        assert path.endswith('/complete'), path
        return {}


def exercise(root, queue_path):
    (root / 'output').mkdir()
    entry = root / 'main.py'
    source = (
        "import json\nfrom pathlib import Path\n"
        "Path('output/result.json').write_text(json.dumps("
        "{'headline':'Checked','status':'ok','count':8,'extra':'not-reported'}))\n"
    )
    entry.write_text(source, encoding='utf-8')
    config = ProjectConfig(
        version=1, project_key='fixture-project', integration_id='fixture-integration',
        display_name='Contract migration acceptance', platform='fixture',
        initial_discovery_fingerprint='fixture-discovery',
        descriptor={'project_key': 'fixture-project'}, descriptor_signature='fixture-signature',
        working_directory='.', command=[sys.executable, 'main.py'],
        result_json='output/result.json',
        fingerprint={'version': 2, 'outputs': ['output/result.json']},
    )
    config.save(root)
    context = TaskContext(root)
    samples = []
    for status in ('completed', 'partial', 'no_change', 'failed'):
        fixture = context.file(f'{status}.json')
        fixture.write_text('{}', encoding='utf-8')
        samples.append({'name': status, 'business_status': status,
                        'fixture': fixture.relative_to(root).as_posix()})
    payload = {
        'schema': 'shopops.result_contract.v1', 'name': 'Synthetic inspection',
        'project_fingerprint': project_fingerprint(root, config=config),
        'fingerprint': config.fingerprint,
        'sources': {'result': {'type': 'json', 'path': 'output/result.json'}},
        'summary': {'headline': {'source': 'result', 'selector': '/headline'}},
        'business_status': {'value': {'source': 'result', 'selector': '/status'},
                            'mapping': {'ok': 'completed'}, 'default': 'failed'},
        'metrics': [{'key': 'count', 'label': 'Checked', 'value_type': 'integer',
                     'visibility': 'public', 'required': True,
                     'value': {'source': 'result', 'selector': '/count'}}],
        'details': [], 'claims': [], 'artifacts': [], 'samples': samples,
    }
    context.contract_path.write_text(yaml.safe_dump(payload), encoding='utf-8')
    config.result_contract = {'version': 1, 'digest': canonical_digest(payload),
                              'project_fingerprint': payload['project_fingerprint'],
                              'status': 'approved'}
    config.save(root)
    original_contract = context.contract_path.read_bytes()
    original_config = context.config_path.read_bytes()
    server = FixtureServer()

    def manage(action, **options):
        return cli._manage_result_contract(
            SimpleNamespace(contract_action=action, **options), context, client=server,
        )

    migration = manage('migrate-schema', target_schema='v2')
    assert migration['submitted'] is False and not server.calls
    assert context.contract_path.read_bytes() == original_contract
    assert context.config_path.read_bytes() == original_config
    assert not (root / 'output/result.json').exists()
    candidate = Path(migration['contract_file'])
    v2 = yaml.safe_load(candidate.read_text(encoding='utf-8'))
    assert v2['reporting_policy'] == reporting_policy(config)
    for key in ('sources', 'summary', 'business_status', 'metrics', 'samples'):
        assert v2[key] == payload[key]
    v2['business_meaning'] = 'Count inspected synthetic records; ok means inspection completed.'
    candidate.write_text(yaml.safe_dump(v2), encoding='utf-8')
    assert manage('validate', contract_file=candidate)['valid']
    server.fail_submission = True
    try:
        manage('submit', contract_file=candidate)
    except ConnectionError:
        pass
    else:
        raise AssertionError('submission must fail while offline')
    assert context.contract_path.read_bytes() == original_contract
    assert context.config_path.read_bytes() == original_config
    server.fail_submission = False
    receipt = manage('submit', contract_file=candidate)
    assert receipt['status'] == 'pending'
    server.contracts[receipt['digest']]['status'] = 'approved'
    approved = manage('submit', contract_file=candidate)
    assert approved['status'] == 'approved' and not approved['created']
    config = ProjectConfig.load(root)
    assert (context.config_dir / 'result-contract.yaml').read_bytes() == original_contract
    assert list(context.config_dir.glob('result-contract.backup-*.yaml'))
    frozen_contract = load_result_contract(root)
    spool = Spool(queue_path)
    fingerprints = []
    for label, code in [('baseline', source), ('comment', '# Comment only\n' + source),
                        ('refactor', source.replace("Path('output/result.json').write_text",
                                                   "target = Path('output/result.json')\ntarget.write_text"))]:
        entry.write_text(code, encoding='utf-8')
        fingerprints.append(project_fingerprint(root, config=config))
        assert run_project(project_dir=root, config=config, spool=spool,
                           local_run_key=label, start_daemon=False, require_tracking=True) == 0
        run = spool.get_run(label)
        assert json.loads(run['result_warnings_json']) == []
        result = json.loads(run['result_json'])
        assert result['contract'] == {'version': approved['version'], 'digest': approved['digest']}
        assert result['metrics'][0]['value'] == 8
        assert 'not-reported' not in json.dumps(result)
        reference = json.loads(run['config_json'])['result_contract']
        assert reference['status'] == 'approved' and reference['run_validated']
        assert reference['snapshot'] == frozen_contract.payload
    assert len(set(fingerprints)) == 3
    assert len(server.contracts) == 1
    # Offline replay must ignore a subsequently edited local contract and policy.
    frozen_contract.path.write_text('invalid later draft', encoding='utf-8')
    config.artifacts.append('output/*.json')
    config.save(root)
    for run in spool.pending_runs():
        Uploader(spool=spool, client=server)._process_run(run)
    assert not spool.pending_runs()
    starts = [body for path, body in server.calls if path.endswith('/start')]
    completions = [body for path, body in server.calls if path.endswith('/complete')]
    assert len(starts) == len(completions) == 3
    for start, fingerprint in zip(starts, fingerprints):
        assert start['project_fingerprint'] == fingerprint
        assert start['result_contract'] == {'version': approved['version'], 'digest': approved['digest']}
        assert start['reporting_policy_digest'] == canonical_digest(v2['reporting_policy'])
    assert all(body['result_warnings'] == [] for body in completions)
    return {'migration': 'passed', 'failed_submission_recovery': 'passed',
            'code_reuse': 'passed', 'offline_snapshot': 'passed',
            'server': 'fixture', 'reporter_version': __version__, 'platform': sys.platform}


def main():
    with tempfile.TemporaryDirectory(prefix='ShopOps contract acceptance ') as directory:
        base = Path(directory).resolve()
        os.environ['SHOPOPS_REPORTER_HOME'] = str(base / 'reporter-home')
        root = base / 'project'
        root.mkdir()
        result = exercise(root, base / 'queue.db')
        print(json.dumps(result))


if __name__ == '__main__':
    main()
