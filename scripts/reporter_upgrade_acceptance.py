"""Real 0.6 -> current installer upgrade with an offline synthetic queue."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
repo = Path(__file__).resolve().parents[1]
plugin = repo/'plugins/shopops-onboarding'
sys.path.insert(0,str(plugin/'tools'))
from shopops_plugin_helper.environment import probe_environment, platform_key
from shopops_plugin_helper.installer import install_reporter, install_preview

def run(args, env):
    return subprocess.run([str(a) for a in args],env=env,check=True,capture_output=True,text=True).stdout

with tempfile.TemporaryDirectory(prefix='shopops-upgrade-') as folder:
    root=Path(folder);home=root/'reporter';project=root/'project';project.mkdir();home.mkdir()
    env={**os.environ,'SHOPOPS_REPORTER_HOME':str(home)}
    # These bytes stand in for existing identity/config; no device enrollment or network calls.
    identity=home/'identity-preservation.fixture';identity.write_bytes(b'existing identity marker')
    config=project/'integration.fixture';config.write_bytes(b'existing project marker')
    old=root/'old';run([sys.executable,'-m','venv',old],env)
    old_python=old/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    probe=probe_environment([sys.executable])
    wheelhouse=plugin/'wheelhouse'/platform_key(probe.os_name, probe.architecture)/f'cp{sys.version_info.major}{sys.version_info.minor}'
    oldwheel=repo/'tests/fixtures/upgrade/shopops_reporter-0.6.0-py3-none-any.whl'
    run([old_python,'-m','pip','install','--no-index','--find-links',wheelhouse,oldwheel],env)
    run([old_python,'-c',"from shopops_reporter.spool import Spool; import sqlite3; s=Spool(); c=sqlite3.connect(s.path); c.execute(\"INSERT INTO local_run(local_run_key,integration_id,project_dir,config_json,project_fingerprint,git_json,environment_json,started_at,created_at) VALUES ('pending','fixture','fixture','{}','fixture','{}','{}','2026-09-09T00:00:00Z',1)\"); c.commit()"],env)
    preview=install_preview(plugin,home,probe)
    installed=install_reporter(plugin,home,probe)
    assert installed.version==preview.version=='0.7.0'
    python=Path(installed.runtime_dir)/'venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    preserved=run([python,'-c',"from shopops_reporter.spool import Spool; s=Spool(); r=s.get_run('pending'); assert r['project_fingerprint']=='fixture' and r['upload_state']=='pending'; print('preserved')"],env)
    assert preserved.strip()=='preserved'
    assert identity.read_bytes()==b'existing identity marker' and config.read_bytes()==b'existing project marker'
    assert old_python.exists()
    assert not install_reporter(plugin,home,probe).changed
    result=run([python,repo/'scripts/external_capability_acceptance.py'],env)
    print(json.dumps({'python':sys.version.split()[0],'upgrade':'0.6.0 -> 0.7.0','queue_preserved':True,'idempotent':True,'acceptance':json.loads(result)}))
