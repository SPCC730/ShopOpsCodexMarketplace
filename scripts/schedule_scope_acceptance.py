"""Offline acceptance against the installed Reporter, without running SOPs."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from shopops_reporter import __version__
from shopops_reporter.daemon import ScheduleSynchronizer
from shopops_reporter.schedule_scope import scoped_tasks
from shopops_reporter.scheduler import SchedulerScanResult

business = {'schedule_key': 'business', 'projects': [{'integration_id': 'sop'}]}
noise = {'schedule_key': 'system', 'task_name': 'WpsUpdateLogonTask', 'projects': []}
assert scoped_tasks([business, noise], {'sop'}) == [business]

class Scanner:
    def scan(self):
        return SchedulerScanResult([business, noise], True)

class Client:
    def __init__(self): self.calls = []
    def signed_json(self, method, path, payload):
        self.calls.append(payload)
        return {}

with tempfile.TemporaryDirectory() as directory:
    pending = Path(directory) / 'pending.json'
    pending.write_text(json.dumps({'tasks': [noise, business], 'scan_complete': True}))
    client = Client()
    with patch('shopops_reporter.schedule_scope.enrolled_integration_ids', return_value={'sop'}):
        assert ScheduleSynchronizer(client, scanner=Scanner(), pending_path=pending).process_once()
    assert [p['tasks'] for p in client.calls] == [[business], [business]]
    assert [p['scan_complete'] for p in client.calls] == [False, True]
    assert not pending.exists()
print(json.dumps({'reporter_version': __version__, 'scope_acceptance': 'passed'}))
