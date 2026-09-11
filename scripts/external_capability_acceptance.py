"""Installed-wheel smoke test; synthetic temporary files only, no network or daemon."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from shopops_reporter import __version__
from shopops_reporter.config import ProjectConfig
from shopops_reporter.runner import run_project
from shopops_reporter.spool import Spool

assert __version__ == '0.7.2'
with tempfile.TemporaryDirectory(prefix='shopops-candidate-') as folder:
    root = Path(folder)
    os.environ['SHOPOPS_REPORTER_HOME'] = str(root / '.reporter')
    fixture = root / 'fixture.py'
    fixture.write_text('''import os
from pathlib import Path
from shopops_reporter.diagnostics import write_run_diagnostic
from shopops_reporter.runtime_probe import write_application_environment
write_application_environment()
Path(os.environ['SHOPOPS_RUN_OUTPUT_DIR'], 'evidence.txt').write_text('synthetic A')
write_run_diagnostic('diagnosis.json', business_status='completed')
''')
    config = ProjectConfig(version=1, project_key='fixture', integration_id='fixture-project',
        display_name='Synthetic fixture', platform='test', working_directory='.',
        command=[sys.executable, str(fixture)], initial_discovery_fingerprint='fixture',
        descriptor={'version': 1}, descriptor_signature='fixture', artifacts=['evidence.txt'],
        diagnostics={'schema_version': 2, 'file': 'diagnosis.json'})
    spool = Spool()
    assert run_project(project_dir=root, config=config, spool=spool, start_daemon=False,
        local_run_key='synthetic-smoke', output_stream=io.BytesIO()) == 0
    row = spool.get_run('synthetic-smoke')
    snapshot = json.loads(row['snapshot_json'])
    assert snapshot['diagnostics']['envelope']['issues'] == []
    assert snapshot['diagnostics']['envelope']['external_run_key'] == 'synthetic-smoke'
    assert len(snapshot['artifacts']) == 1
    frozen = Path(row['snapshot_dir']) / snapshot['artifacts'][0]['path']
    (root / 'evidence.txt').write_text('synthetic B')
    assert frozen.read_text() == 'synthetic A'
    print(json.dumps({'version': __version__, 'python': sys.version.split()[0],
        'diagnostics_v2': True, 'snapshot_preserved': True, 'network_calls': 0}))
