"""Install and activate Reporter without running or rewriting business tasks."""
from __future__ import annotations

import json
import os
import shlex
import stat
import subprocess
from dataclasses import asdict
from pathlib import Path

from .installer import InstallError, _runtime_layout, install_preview, install_reporter


def _run(python: Path, home: Path, arguments: list[str]) -> dict:
    # An inherited developer PYTHONPATH must not turn this check into a probe
    # of source checkout code rather than the installed wheel.
    env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "PYTHONHOME"}}
    env["SHOPOPS_REPORTER_HOME"] = str(home)
    try:
        completed = subprocess.run(
            [str(python), *arguments], env=env, capture_output=True,
            text=True, timeout=60, check=False,
        )
        value = json.loads(completed.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        raise InstallError("activation_check_failed") from error
    if completed.returncode != 0 or not isinstance(value, dict):
        # Do not echo stdout/stderr: project registry parsing may contain paths
        # or private configuration in exception messages.
        raise InstallError("activation_command_failed")
    return value


def activation_check(plugin: Path, home: Path, probe) -> dict:
    home = home.expanduser().resolve()
    preview = install_preview(plugin, home, probe)
    layout = _runtime_layout(probe)
    python = Path(preview.runtime_dir) / "venv" / layout.scripts_directory / layout.python_name
    if not python.is_file():
        return {"target_version": preview.version, "state": "not_installed"}
    value = _run(python, home, [str(Path(__file__).with_name("activation_probe.py"))])
    value["target_version"] = preview.version
    shim = Path(preview.shim_path)
    binary = python.parent / layout.runtime_launcher_name
    if layout.windows:
        relative = os.path.relpath(binary, shim.parent).replace("/", "\\")
        expected = f'@echo off\ncall "%~dp0{relative}" %*\nexit /b %ERRORLEVEL%\n'
    else:
        expected = f'#!/bin/sh\nexec {shlex.quote(str(binary))} "$@"\n'
    try:
        value["stable_shim_verified"] = not shim.is_symlink() and shim.read_text(encoding="utf-8") == expected and (
            layout.windows or stat.S_IMODE(shim.stat().st_mode) == 0o700
        )
    except OSError:
        value["stable_shim_verified"] = False
    daemon = value["daemon"]
    value["activation_verified"] = (
        value["installed_version"] == preview.version
        and value["stable_shim_verified"]
        and daemon["state"] == "healthy"
        and daemon["runtime_version"] == preview.version
    )
    return value


def upgrade_reporter(plugin: Path, home: Path, probe, *, start_background: bool = False) -> dict:
    # install_reporter also repairs the stable shim when this version is
    # already installed. Never return early just because the wheel is current.
    installed = install_reporter(plugin, home, probe)
    before = activation_check(plugin, home, probe)
    daemon = before["daemon"]
    if daemon["state"] not in {"healthy", "stopped", "stale"}:
        raise InstallError("activation_requires_daemon_identity_review")
    if daemon["state"] == "healthy" and daemon["runtime_version"] is None:
        raise InstallError("activation_requires_daemon_runtime_review")
    layout = _runtime_layout(probe)
    python = Path(installed.runtime_dir) / "venv" / layout.scripts_directory / layout.python_name
    restarted = daemon["state"] == "healthy" and daemon["runtime_version"] != installed.version
    if restarted:
        _run(python, home, [str(Path(__file__).with_name("activation_probe.py")), "stop"])
    if restarted or (start_background and daemon["state"] in {"stopped", "stale"}):
        _run(python, home, ["-m", "shopops_reporter", "--json", "start"])
    after = activation_check(plugin, home, probe)
    if (restarted or start_background or daemon["state"] == "healthy") and not after["activation_verified"]:
        raise InstallError("activation_version_not_verified")
    return {"install": asdict(installed), "restarted": restarted, "activation": after}
