"""Behavioral coverage for offline, atomic Reporter installation."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from shopops_plugin_helper import __main__, installer
from shopops_plugin_helper.environment import EnvironmentProbe
from shopops_plugin_helper.installer import InstallError, InstallResult, install_reporter, self_check


@pytest.fixture
def supported_probe() -> EnvironmentProbe:
    return EnvironmentProbe(
        os_name="Darwin",
        architecture="arm64",
        python_executable=sys.executable,
        python_version="3.12.0",
        python_architecture="arm64",
        python_platform="macosx-15.0-arm64",
        supported=True,
        reason=None,
    )


@pytest.fixture
def windows_probe() -> EnvironmentProbe:
    return EnvironmentProbe(
        os_name="Windows",
        architecture="AMD64",
        python_executable="C:\\Python311\\python.exe",
        python_version="3.11.15",
        python_architecture="AMD64",
        python_platform="win-amd64",
        supported=True,
        reason=None,
    )


def write_fake_wheel(path: Path, version: str) -> None:
    """Create a tiny offline wheel with the real Reporter console-script name."""
    dist_info = f"shopops_reporter-{version}.dist-info"
    with ZipFile(path, "w", ZIP_DEFLATED) as wheel:
        wheel.writestr("shopops_reporter/__init__.py", f"__version__ = '{version}'\n")
        wheel.writestr("shopops_reporter/__main__.py", "from .cli import main\nraise SystemExit(main())\n")
        wheel.writestr(
            "shopops_reporter/cli.py",
            "import json\n"
            "from . import __version__\n"
            "def main():\n"
            "    print(json.dumps({'schema': 'shopops.reporter.cli.v1', "
            "'reporter_version': __version__, 'ok': False, 'action': 'status', "
            "'error': {'code': 'not_paired', 'message': 'not paired'}}))\n"
            "    return 2\n",
        )
        wheel.writestr(
            f"{dist_info}/METADATA",
            f"Metadata-Version: 2.1\nName: shopops-reporter\nVersion: {version}\n",
        )
        wheel.writestr(
            f"{dist_info}/WHEEL",
            "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        )
        wheel.writestr(f"{dist_info}/entry_points.txt", "[console_scripts]\nshopops-report = shopops_reporter.cli:main\n")
        wheel.writestr(f"{dist_info}/RECORD", "")


def fake_wheelhouse(tmp_path: Path, *, tampered: bool = False, version: str = "0.1.0") -> tuple[dict[str, object], Path]:
    plugin_root = tmp_path / "plugin"
    entries = []
    checksums: dict[str, str] = {}
    for platform_name in ("macos-arm64", "windows-x64"):
        for abi in ("cp311", "cp312"):
            wheel_dir = plugin_root / "wheelhouse" / platform_name / abi
            wheel_dir.mkdir(parents=True)
            wheel = wheel_dir / f"shopops_reporter-{version}-py3-none-any.whl"
            write_fake_wheel(wheel, version)
            digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
            entries.append(
                {
                    "platform": platform_name,
                    "python": abi.removeprefix("cp"),
                    "reporter_version": version,
                    "files": [{"name": wheel.name, "sha256": digest}],
                }
            )
            checksums[f"wheelhouse/{platform_name}/{abi}/{wheel.name}"] = digest

    manifest: dict[str, object] = {"wheelhouses": entries}
    (plugin_root / "reporter-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (plugin_root / "checksums.json").write_text(json.dumps(checksums), encoding="utf-8")
    if tampered:
        wheel = plugin_root / "wheelhouse/macos-arm64/cp312" / f"shopops_reporter-{version}-py3-none-any.whl"
        wheel.write_bytes(wheel.read_bytes() + b"tampered")
    return manifest, plugin_root


def fake_plugin_root(tmp_path: Path) -> Path:
    return fake_wheelhouse(tmp_path)[1]


def install_fake_version(tmp_path: Path, version: str) -> Path:
    runtime = tmp_path / "home" / "runtime" / version
    executable = runtime / "venv" / "bin" / "shopops-report"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o700)
    shim = tmp_path / "home" / "bin" / "shopops-report"
    shim.parent.mkdir(parents=True)
    shim.write_text(f"#!/bin/sh\nexec '{executable}' \"$@\"\n", encoding="utf-8")
    shim.chmod(0o700)
    return runtime


def read_current_target(reporter_home: Path) -> Path:
    shim = (reporter_home / "bin" / "shopops-report").read_text(encoding="utf-8")
    return Path(shim.split("exec '", 1)[1].split("'", 1)[0]).parents[2]


def test_install_rejects_a_tampered_wheel(tmp_path, supported_probe):
    _, plugin_root = fake_wheelhouse(tmp_path, tampered=True)
    with pytest.raises(InstallError, match="checksum_mismatch"):
        install_reporter(plugin_root, tmp_path / "home", supported_probe)


def test_failed_self_check_keeps_previous_shim(tmp_path, supported_probe, monkeypatch):
    old = install_fake_version(tmp_path, "0.0.9")
    monkeypatch.setattr(installer, "self_check", lambda _python, _version: False)
    with pytest.raises(InstallError, match="self_check_failed"):
        install_reporter(fake_plugin_root(tmp_path), tmp_path / "home", supported_probe)
    assert read_current_target(tmp_path / "home") == old


def test_reporter_survives_plugin_source_removal(tmp_path, supported_probe):
    plugin_root = fake_plugin_root(tmp_path)
    result = install_reporter(plugin_root, tmp_path / "home", supported_probe)
    shutil.rmtree(plugin_root)
    completed = subprocess.run([result.shim_path, "--json", "status"], capture_output=True, text=True)
    assert completed.returncode in (0, 2)
    assert json.loads(completed.stdout)["action"] == "status"


def test_install_rechecks_a_whitespace_safe_final_launcher(tmp_path, supported_probe):
    _, plugin_root = fake_wheelhouse(tmp_path)
    reporter_home = tmp_path / "Reporter Home"

    result = install_reporter(plugin_root, reporter_home, supported_probe)
    completed = subprocess.run([result.shim_path, "--json", "status"], capture_output=True, text=True)

    assert completed.returncode == 2
    assert json.loads(completed.stdout)["action"] == "status"
    launcher = (reporter_home / "runtime" / "0.1.0" / "venv" / "bin" / "shopops-report").read_text()
    assert launcher.startswith("#!/bin/sh\nexec '")


def test_install_is_idempotent_after_a_healthy_versioned_runtime(tmp_path, supported_probe):
    _, plugin_root = fake_wheelhouse(tmp_path)
    first = install_reporter(plugin_root, tmp_path / "home", supported_probe)
    second = install_reporter(plugin_root, tmp_path / "home", supported_probe)

    assert first.changed is True
    assert second == InstallResult(
        version="0.1.0",
        runtime_dir=str(tmp_path / "home" / "runtime" / "0.1.0"),
        shim_path=str(tmp_path / "home" / "bin" / "shopops-report"),
        changed=False,
    )
    assert stat.S_IMODE((tmp_path / "home" / "bin" / "shopops-report").stat().st_mode) == 0o700


def test_windows_preview_uses_cmd_shim_and_windows_wheelhouse(tmp_path, windows_probe):
    plugin_root = fake_plugin_root(tmp_path)

    preview = installer.install_preview(plugin_root, tmp_path / "home", windows_probe)

    assert preview.version == "0.1.0"
    assert preview.runtime_dir == str(tmp_path / "home" / "runtime" / "0.1.0")
    assert preview.shim_path == str(tmp_path / "home" / "bin" / "shopops-report.cmd")


def test_windows_install_writes_relative_runtime_launcher_and_stable_cmd_shim(
    tmp_path, windows_probe, monkeypatch
):
    plugin_root = fake_plugin_root(tmp_path)
    reporter_home = tmp_path / "Reporter Home"

    def fake_create_venv(_python_executable, venv):
        scripts = venv / "Scripts"
        scripts.mkdir(parents=True)
        (scripts / "python.exe").touch()

    monkeypatch.setattr(installer, "_create_venv", fake_create_venv)
    monkeypatch.setattr(installer, "_install_offline", lambda *_args: None)
    monkeypatch.setattr(installer, "self_check", lambda binary, _version: binary.is_file())

    result = install_reporter(plugin_root, reporter_home, windows_probe)

    runtime_launcher = reporter_home / "runtime/0.1.0/venv/Scripts/shopops-report.cmd"
    stable_shim = reporter_home / "bin/shopops-report.cmd"
    assert result.shim_path == str(stable_shim)
    assert runtime_launcher.read_text(encoding="utf-8") == (
        "@echo off\n\"%~dp0python.exe\" -m shopops_reporter %*\nexit /b %ERRORLEVEL%\n"
    )
    assert stable_shim.read_text(encoding="utf-8") == (
        '@echo off\ncall "%~dp0..\\runtime\\0.1.0\\venv\\Scripts\\shopops-report.cmd" %*\n'
        "exit /b %ERRORLEVEL%\n"
    )


def test_self_check_rejects_legacy_text_based_unpaired_status(tmp_path, monkeypatch):
    reporter_binary = tmp_path / "home" / "runtime" / "0.1.0" / "venv" / "bin" / "shopops-report"
    reporter_binary.parent.mkdir(parents=True)
    reporter_binary.touch()

    class CompletedProcess:
        returncode = 2
        stdout = json.dumps(
            {
                "action": "status",
                "error": {"code": "runtime_error", "message": "Reporter \u5c1a\u672a\u914d\u5bf9"},
            }
        )

    monkeypatch.setattr(installer.subprocess, "run", lambda *_args, **_kwargs: CompletedProcess())

    assert self_check(reporter_binary, "0.1.0") is False


def test_windows_self_check_invokes_the_versioned_venv_python_directly(tmp_path, monkeypatch):
    reporter_binary = tmp_path / "home/runtime/0.1.0/venv/Scripts/shopops-report.cmd"
    reporter_binary.parent.mkdir(parents=True)
    reporter_binary.touch()
    (reporter_binary.parent / "python.exe").touch()
    captured_command = None

    class CompletedProcess:
        returncode = 2
        stdout = json.dumps(
            {
                "schema": "shopops.reporter.cli.v1",
                "reporter_version": "0.1.0",
                "ok": False,
                "action": "status",
                "error": {"code": "not_paired", "message": "not paired"},
            }
        )

    def run(command, **_kwargs):
        nonlocal captured_command
        captured_command = command
        return CompletedProcess()

    monkeypatch.setattr(installer.subprocess, "run", run)

    assert self_check(reporter_binary, "0.1.0") is True
    assert captured_command == [
        str(reporter_binary.parent / "python.exe"),
        "-m",
        "shopops_reporter",
        "--json",
        "status",
    ]


@pytest.mark.parametrize(
    ("returncode", "payload", "expected"),
    [
        (
            0,
            {
                "schema": "shopops.reporter.cli.v1",
                "reporter_version": "0.1.0",
                "ok": True,
                "action": "status",
                "data": {"daemon": {"running": False}},
            },
            True,
        ),
        (
            2,
            {
                "schema": "shopops.reporter.cli.v1",
                "reporter_version": "0.1.0",
                "ok": False,
                "action": "status",
                "error": {"code": "not_paired", "message": "not paired"},
            },
            True,
        ),
        (
            0,
            {
                "reporter_version": "0.1.0",
                "ok": True,
                "action": "status",
                "data": {},
            },
            False,
        ),
        (
            0,
            {
                "schema": "shopops.reporter.cli.v1",
                "reporter_version": "9.9.9",
                "ok": True,
                "action": "status",
                "data": {},
            },
            False,
        ),
        (
            2,
            {
                "schema": "shopops.reporter.cli.v1",
                "reporter_version": "0.1.0",
                "ok": True,
                "action": "status",
                "error": {"code": "not_paired", "message": "not paired"},
            },
            False,
        ),
        (
            2,
            {
                "schema": "shopops.reporter.cli.v1",
                "reporter_version": "0.1.0",
                "ok": False,
                "action": "status",
                "error": {"code": "runtime_error", "message": "not paired"},
            },
            False,
        ),
    ],
)
def test_self_check_requires_exact_reporter_protocol(
    tmp_path, monkeypatch, returncode, payload, expected
):
    reporter_binary = tmp_path / "home/runtime/0.1.0/venv/bin/shopops-report"
    reporter_binary.parent.mkdir(parents=True)
    reporter_binary.touch()

    class CompletedProcess:
        stdout = json.dumps(payload)

    CompletedProcess.returncode = returncode
    monkeypatch.setattr(installer.subprocess, "run", lambda *_args, **_kwargs: CompletedProcess())

    assert self_check(reporter_binary, "0.1.0") is expected


def test_install_command_requires_the_exact_manifest_version(monkeypatch, capsys, tmp_path, supported_probe):
    expected = InstallResult("0.1.0", "/runtime", "/shim", False)
    monkeypatch.setattr(__main__, "probe_environment", lambda: supported_probe)
    monkeypatch.setattr(__main__, "install_preview", lambda *_args: expected)
    monkeypatch.setattr(__main__, "default_reporter_home", lambda: tmp_path / "home")

    assert __main__.main(["install", "--confirm-version", "0.1.1", "--json"]) == 2

    assert json.loads(capsys.readouterr().out) == {
        "schema_version": 1,
        "error": "confirmation_version_mismatch",
        "version": "0.1.0",
    }


def test_install_preview_and_confirmed_install_emit_result(monkeypatch, capsys, tmp_path, supported_probe):
    preview = InstallResult("0.1.0", "/runtime", "/shim", False)
    installed = InstallResult("0.1.0", "/runtime", "/shim", True)
    monkeypatch.setattr(__main__, "probe_environment", lambda: supported_probe)
    monkeypatch.setattr(__main__, "install_preview", lambda *_args: preview)
    monkeypatch.setattr(__main__, "install_reporter", lambda *_args: installed)
    monkeypatch.setattr(__main__, "default_reporter_home", lambda: tmp_path / "home")

    assert __main__.main(["install-preview", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "schema_version": 1,
        "install": {"version": "0.1.0", "runtime_dir": "/runtime", "shim_path": "/shim", "changed": False},
    }

    assert __main__.main(["install", "--confirm-version", "0.1.0", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "schema_version": 1,
        "install": {"version": "0.1.0", "runtime_dir": "/runtime", "shim_path": "/shim", "changed": True},
    }


def test_install_preview_cli_supports_system_python39():
    """The documented python3 entrypoint must work with macOS's Python 3.9."""
    python3 = shutil.which("python3")
    if python3 is None:
        pytest.skip("python3 is not available")
    version = tuple(
        json.loads(
            subprocess.check_output(
                [python3, "-c", "import json, sys; print(json.dumps(list(sys.version_info[:2])))"],
                text=True,
            )
        )
    )
    if version >= (3, 10):
        pytest.skip("system python3 is not an affected pre-3.10 runtime")

    plugin_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [python3, "-m", "shopops_plugin_helper", "install-preview", "--json"],
        cwd=plugin_root,
        env={**os.environ, "PYTHONPATH": "tools"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["schema_version"] == 1
    assert payload["install"]["version"] == "0.1.4"


@pytest.mark.parametrize("command", ["probe", "install-preview", "install"])
def test_helper_normalizes_filesystem_failures_as_json(
    monkeypatch, capsys, tmp_path, supported_probe, command
):
    preview = InstallResult("0.1.0", "/runtime", "/shim", False)
    monkeypatch.setattr(__main__, "probe_environment", lambda: supported_probe)
    monkeypatch.setattr(__main__, "default_reporter_home", lambda: tmp_path / "home")
    monkeypatch.setattr(__main__, "install_preview", lambda *_args: preview)
    argv = [command, "--json"]
    if command == "probe":
        monkeypatch.setattr(
            __main__, "probe_environment", lambda: (_ for _ in ()).throw(PermissionError("denied"))
        )
    elif command == "install-preview":
        monkeypatch.setattr(
            __main__, "install_preview", lambda *_args: (_ for _ in ()).throw(PermissionError("denied"))
        )
    else:
        argv = ["install", "--confirm-version", "0.1.0", "--json"]
        monkeypatch.setattr(
            __main__, "install_reporter", lambda *_args: (_ for _ in ()).throw(PermissionError("denied"))
        )

    assert __main__.main(argv) == 2

    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"schema_version": 1, "error": "filesystem_error"}
    assert captured.err == ""
