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


def test_probe_accepts_windows_x64_with_python_311(monkeypatch):
    """A 64-bit Windows interpreter can consume the locked Windows wheels."""
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(platform, "machine", lambda: "AMD64")

    class CompletedProcess:
        returncode = 0
        stdout = (
            '{"implementation": "cpython", "version_info": [3, 11, 15], '
            '"python_architecture": "AMD64", "python_platform": "win-amd64", '
            '"python_executable": "C:\\\\Python311\\\\python.exe"}'
        )

    monkeypatch.setattr(
        "shopops_plugin_helper.environment.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(),
    )

    probe = probe_environment(candidates=[("py", "-3.11")])

    assert probe.supported is True
    assert probe.python_executable == "C:\\Python311\\python.exe"
    assert probe.python_version == "3.11.15"
    assert probe.python_architecture == "AMD64"
    assert probe.python_platform == "win-amd64"
    assert probe.reason is None


def test_probe_rejects_32_bit_python_on_windows_x64(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(platform, "machine", lambda: "AMD64")

    class CompletedProcess:
        returncode = 0
        stdout = (
            '{"implementation": "cpython", "version_info": [3, 12, 8], '
            '"python_architecture": "x86", "python_platform": "win32", '
            '"python_executable": "C:\\\\Python312-32\\\\python.exe"}'
        )

    monkeypatch.setattr(
        "shopops_plugin_helper.environment.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(),
    )

    probe = probe_environment(candidates=[("py", "-3.12-32")])

    assert probe.supported is False
    assert probe.reason == "unsupported_python"


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
            '{"implementation": "cpython", "version_info": [3, 10, 14], '
            '"python_architecture": "arm64", "python_platform": "macosx-15.0-arm64"}',
            '{"implementation": "cpython", "version_info": [3, 11, 9], '
            '"python_architecture": "arm64", "python_platform": "macosx-15.0-arm64"}',
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
    assert probe.python_architecture == "arm64"
    assert probe.python_platform == "macosx-15.0-arm64"
    assert probe.reason is None


def test_probe_skips_rosetta_python_and_selects_later_native_arm64_candidate(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")
    responses = iter(
        [
            '{"implementation": "cpython", "version_info": [3, 12, 8], '
            '"python_architecture": "x86_64", "python_platform": "macosx-15.0-x86_64"}',
            '{"implementation": "cpython", "version_info": [3, 11, 9], '
            '"python_architecture": "arm64", "python_platform": "macosx-14.0-arm64"}',
        ]
    )

    class CompletedProcess:
        returncode = 0

        def __init__(self, stdout):
            self.stdout = stdout

    monkeypatch.setattr(
        "shopops_plugin_helper.environment.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(next(responses)),
    )

    probe = probe_environment(candidates=["rosetta-python", "native-python"])

    assert probe.supported is True
    assert probe.python_executable == "native-python"
    assert probe.python_architecture == "arm64"
    assert probe.python_platform == "macosx-14.0-arm64"


def test_probe_reports_unsupported_python_when_no_candidate_is_compatible(monkeypatch):
    """A supported platform without CPython 3.11 or 3.12 remains unsupported."""
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")

    class CompletedProcess:
        stdout = (
            '{"implementation": "pypy", "version_info": [3, 12, 2], '
            '"python_architecture": "arm64", "python_platform": "macosx-15.0-arm64"}'
        )
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
        stdout = (
            '{"implementation": "cpython", "version_info": [3, 12, 8], '
            '"python_architecture": "arm64", "python_platform": "macosx-15.0-arm64"}'
        )
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
        stdout = (
            f'{{"implementation": "cpython", "version_info": {version_info}, '
            '"python_architecture": "arm64", "python_platform": "macosx-15.0-arm64"}'
        )
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


@pytest.mark.parametrize(
    "payload",
    [
        '{"implementation": "cpython", "version_info": [3, 12, 8], '
        '"python_platform": "macosx-15.0-arm64"}',
        '{"implementation": "cpython", "version_info": [3, 12, 8], '
        '"python_architecture": true, "python_platform": "macosx-15.0-arm64"}',
        '{"implementation": "cpython", "version_info": [3, 12, 8], '
        '"python_architecture": "arm64", "python_platform": ["macosx-15.0-arm64"]}',
    ],
)
def test_probe_rejects_malformed_architecture_payload(monkeypatch, payload):
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")

    class CompletedProcess:
        returncode = 0
        stdout = payload

    monkeypatch.setattr(
        "shopops_plugin_helper.environment.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(),
    )

    probe = probe_environment(candidates=["malformed-python"])

    assert probe.supported is False
    assert probe.reason == "unsupported_python"


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
            python_architecture="arm64",
            python_platform="macosx-15.0-arm64",
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
            "python_architecture": "arm64",
            "python_platform": "macosx-15.0-arm64",
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
            python_architecture=None,
            python_platform=None,
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
            "python_architecture": None,
            "python_platform": None,
            "supported": False,
            "reason": "unsupported_platform",
        },
    }
