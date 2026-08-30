"""Behavioral coverage for the ShopOps installation environment probe."""

from __future__ import annotations

import json
import platform
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from shopops_plugin_helper import __main__
from shopops_plugin_helper.environment import probe_environment


def test_probe_accepts_apple_silicon_with_python_312(monkeypatch):
    """A supported Mac with CPython 3.12 is accepted for installation."""
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")

    probe = probe_environment(candidates=[sys.executable])

    assert probe.supported is True
    assert probe.python_executable == sys.executable
    assert probe.python_version.startswith("3.12")
    assert probe.reason is None


def test_probe_rejects_intel_mac(monkeypatch):
    """Intel Macs are rejected before attempting Python discovery."""
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "x86_64")

    probe = probe_environment(candidates=[])

    assert probe.supported is False
    assert probe.reason == "unsupported_platform"
    assert probe.python_executable is None
    assert probe.python_version is None


def test_probe_skips_incompatible_interpreter_and_uses_next_candidate(monkeypatch):
    """A compatible later candidate wins after an unsupported interpreter."""
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")

    responses = iter(
        [
            '{"implementation": "cpython", "version_info": [3, 10, 14]}',
            '{"implementation": "cpython", "version_info": [3, 11, 9]}',
        ]
    )

    class CompletedProcess:
        def __init__(self, stdout):
            self.stdout = stdout
            self.returncode = 0

    monkeypatch.setattr(
        "shopops_plugin_helper.environment.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(next(responses)),
    )

    probe = probe_environment(candidates=["python-old", "python-supported"])

    assert probe.supported is True
    assert probe.python_executable == "python-supported"
    assert probe.python_version == "3.11.9"
    assert probe.reason is None


def test_probe_reports_unsupported_python_when_no_candidate_is_compatible(monkeypatch):
    """A supported platform without CPython 3.11 or 3.12 remains unsupported."""
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")

    class CompletedProcess:
        stdout = '{"implementation": "pypy", "version_info": [3, 12, 2]}'
        returncode = 0

    monkeypatch.setattr(
        "shopops_plugin_helper.environment.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(),
    )

    probe = probe_environment(candidates=["pypy3"])

    assert probe.supported is False
    assert probe.reason == "unsupported_python"
    assert probe.python_executable is None
    assert probe.python_version is None


def test_probe_ignores_a_failed_interpreter_process(monkeypatch):
    """A failed candidate cannot be accepted from incidental standard output."""
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")

    class CompletedProcess:
        stdout = '{"implementation": "cpython", "version_info": [3, 12, 8]}'
        returncode = 1

    monkeypatch.setattr(
        "shopops_plugin_helper.environment.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(),
    )

    probe = probe_environment(candidates=["broken-python"])

    assert probe.supported is False
    assert probe.reason == "unsupported_python"


@pytest.mark.parametrize(
    "version_info",
    ["[3, 12, true]", "[3, 12, -1]"],
)
def test_probe_rejects_invalid_version_components(monkeypatch, version_info):
    """Boolean and negative version components cannot make a candidate valid."""
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")

    class CompletedProcess:
        stdout = f'{{"implementation": "cpython", "version_info": {version_info}}}'
        returncode = 0

    monkeypatch.setattr(
        "shopops_plugin_helper.environment.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(),
    )

    probe = probe_environment(candidates=["invalid-python"])

    assert probe.supported is False
    assert probe.reason == "unsupported_python"
    assert probe.python_executable is None
    assert probe.python_version is None


def test_probe_json_emits_only_a_versioned_machine_readable_envelope(monkeypatch, capsys):
    """The CLI provides a stable JSON-only result for installer automation."""
    monkeypatch.setattr(
        __main__,
        "probe_environment",
        lambda: __main__.EnvironmentProbe(
            os_name="Darwin",
            architecture="arm64",
            python_executable="/usr/local/bin/python3.12",
            python_version="3.12.8",
            supported=True,
            reason=None,
        ),
    )

    assert __main__.main(["probe", "--json"]) == 0

    assert json.loads(capsys.readouterr().out) == {
        "schema_version": 1,
        "environment": {
            "os_name": "Darwin",
            "architecture": "arm64",
            "python_executable": "/usr/local/bin/python3.12",
            "python_version": "3.12.8",
            "supported": True,
            "reason": None,
        },
    }


def test_probe_json_reports_unsupported_environment_with_nonzero_exit(monkeypatch, capsys):
    """Installer automation receives one JSON result when the platform is unsupported."""
    monkeypatch.setattr(
        __main__,
        "probe_environment",
        lambda: __main__.EnvironmentProbe(
            os_name="Darwin",
            architecture="x86_64",
            python_executable=None,
            python_version=None,
            supported=False,
            reason="unsupported_platform",
        ),
    )

    assert __main__.main(["probe", "--json"]) == 1

    assert json.loads(capsys.readouterr().out) == {
        "schema_version": 1,
        "environment": {
            "os_name": "Darwin",
            "architecture": "x86_64",
            "python_executable": None,
            "python_version": None,
            "supported": False,
            "reason": "unsupported_platform",
        },
    }
