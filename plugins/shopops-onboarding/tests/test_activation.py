from pathlib import Path
from types import SimpleNamespace

import pytest
from shopops_plugin_helper import activation
from shopops_plugin_helper.activation_probe import classify_launcher
from shopops_plugin_helper.installer import InstallError, InstallResult


@pytest.mark.parametrize('content,state', [
    ('canonical\r\n', 'stable_entrypoint'),
    ('/Users/a/.shopops-reporter/runtime/0.6.0/venv/bin/shopops-report run', 'pinned_runtime'),
    (r'& "C:\Users\a\AppData\Local\ShopOps\Reporter\runtime\0.6.0\venv\Scripts\shopops-report.exe" run', 'pinned_runtime'),
    ('python -m shopops_reporter run', 'custom_entrypoint_review_required'),
    ('shopops-report run', 'custom_entrypoint_review_required'),
    ('arbitrary command', 'unknown_entrypoint'),
])
def test_launcher_audit_never_treats_custom_or_pinned_invocation_as_stable(content, state):
    assert classify_launcher(content, 'canonical\n') == state


def setup_upgrade(monkeypatch, *, state='healthy', version='0.6.0', after_version='0.7.0'):
    calls = []
    installed = InstallResult('0.7.0', '/reporter/runtime/0.7.0', '/reporter/bin/shopops-report', False)
    monkeypatch.setattr(activation, 'install_reporter', lambda *a: calls.append('install') or installed)
    monkeypatch.setattr(activation, '_runtime_layout', lambda p: SimpleNamespace(scripts_directory='bin', python_name='python'))
    before = {'daemon': {'state': state, 'runtime_version': version}, 'activation_verified': version == '0.7.0'}
    after = {'daemon': {'state': 'healthy', 'runtime_version': after_version}, 'activation_verified': after_version == '0.7.0'}
    checks = iter([before, after])
    monkeypatch.setattr(activation, 'activation_check', lambda *a: next(checks))
    monkeypatch.setattr(activation, '_run', lambda python, home, args: calls.append(args[-1]) or {})
    return calls


def test_current_install_does_not_hide_old_daemon(monkeypatch):
    calls = setup_upgrade(monkeypatch)
    result = activation.upgrade_reporter(Path('/plugin'), Path('/reporter'), None)
    assert calls == ['install', 'stop', 'start']
    assert result['restarted'] and result['activation']['activation_verified']


def test_current_daemon_is_not_restarted(monkeypatch):
    calls = setup_upgrade(monkeypatch, version='0.7.0')
    assert not activation.upgrade_reporter(Path('/plugin'), Path('/reporter'), None)['restarted']
    assert calls == ['install']


@pytest.mark.parametrize('state', ['foreign', 'unknown', 'unhealthy', 'legacy_unverified'])
def test_unverified_daemon_never_stopped_or_started(monkeypatch, state):
    calls = setup_upgrade(monkeypatch, state=state)
    with pytest.raises(InstallError, match='identity_review'):
        activation.upgrade_reporter(Path('/plugin'), Path('/reporter'), None)
    assert calls == ['install']


def test_unknown_runtime_is_not_assumed_current(monkeypatch):
    calls = setup_upgrade(monkeypatch, version=None)
    with pytest.raises(InstallError, match='runtime_review'):
        activation.upgrade_reporter(Path('/plugin'), Path('/reporter'), None)
    assert calls == ['install']


@pytest.mark.parametrize('start', [False, True])
def test_stopped_daemon_needs_start_option(monkeypatch, start):
    calls = setup_upgrade(monkeypatch, state='stopped', version=None)
    activation.upgrade_reporter(Path('/plugin'), Path('/reporter'), None, start_background=start)
    assert calls == (['install', 'start'] if start else ['install'])


def test_failed_stop_does_not_start_replacement(monkeypatch):
    calls = setup_upgrade(monkeypatch)
    def fail(*args):
        raise InstallError('activation_command_failed')
    monkeypatch.setattr(activation, '_run', fail)
    with pytest.raises(InstallError):
        activation.upgrade_reporter(Path('/plugin'), Path('/reporter'), None)
    assert calls == ['install']


def test_old_version_after_restart_cannot_report_success(monkeypatch):
    setup_upgrade(monkeypatch, after_version='0.6.0')
    with pytest.raises(InstallError, match='version_not_verified'):
        activation.upgrade_reporter(Path('/plugin'), Path('/reporter'), None)
