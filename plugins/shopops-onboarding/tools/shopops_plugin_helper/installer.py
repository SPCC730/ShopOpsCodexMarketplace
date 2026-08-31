"""Install the checksum-locked ShopOps Reporter without contacting an index."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import tempfile
from typing import Any

from .environment import EnvironmentProbe, is_arm64_compatible


_PLATFORM = "macos-arm64"
_REPORTER_SCHEMA = "shopops.reporter.cli.v1"
_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")


class InstallError(RuntimeError):
    """The locked Reporter payload could not be installed safely."""


@dataclass(frozen=True)
class InstallResult:
    """The active Reporter runtime and stable command path."""

    version: str
    runtime_dir: str
    shim_path: str
    changed: bool


@dataclass(frozen=True)
class _LockedWheelhouse:
    version: str
    directory: Path


def default_reporter_home() -> Path:
    """Return the user-owned Reporter state directory."""
    return Path.home() / ".shopops-reporter"


def install_preview(
    plugin_root: Path, reporter_home: Path, probe: EnvironmentProbe
) -> InstallResult:
    """Validate the selected offline lock and report the install destination."""
    locked = _locked_wheelhouse(plugin_root, probe)
    runtime_dir = reporter_home / "runtime" / locked.version
    return InstallResult(
        version=locked.version,
        runtime_dir=str(runtime_dir),
        shim_path=str(reporter_home / "bin" / "shopops-report"),
        changed=False,
    )


def install_reporter(
    plugin_root: Path, reporter_home: Path, probe: EnvironmentProbe
) -> InstallResult:
    """Install a verified Reporter runtime and atomically make it current."""
    locked = _locked_wheelhouse(plugin_root, probe)
    reporter_home = reporter_home.expanduser().resolve()
    runtime_root = reporter_home / "runtime"
    runtime_dir = runtime_root / locked.version
    reporter_binary = runtime_dir / "venv" / "bin" / "shopops-report"
    shim_path = reporter_home / "bin" / "shopops-report"

    if reporter_binary.is_file() and self_check(reporter_binary, locked.version):
        changed = _ensure_shim(shim_path, reporter_binary)
        return InstallResult(locked.version, str(runtime_dir), str(shim_path), changed)

    runtime_root.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(tempfile.mkdtemp(prefix=f".{locked.version}.", dir=runtime_root))
    backup_dir: Path | None = None
    installed_runtime = False
    try:
        staging_venv = staging_dir / "venv"
        _create_venv(probe.python_executable, staging_venv)
        _install_offline(staging_venv / "bin" / "python", locked)
        staged_binary = staging_venv / "bin" / "shopops-report"
        if not self_check(staged_binary, locked.version):
            raise InstallError("self_check_failed")

        if runtime_dir.exists():
            backup_dir = Path(tempfile.mkdtemp(prefix=f".{locked.version}.backup.", dir=runtime_root))
            backup_dir.rmdir()
            os.replace(runtime_dir, backup_dir)
        os.replace(staging_dir, runtime_dir)
        installed_runtime = True
        _relocate_console_script(reporter_binary)
        if not self_check(reporter_binary, locked.version):
            raise InstallError("self_check_failed")
        _ensure_shim(shim_path, reporter_binary)
    except Exception:
        if installed_runtime:
            _remove_path(runtime_dir)
        if backup_dir is not None and backup_dir.exists():
            os.replace(backup_dir, runtime_dir)
        raise
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        if backup_dir is not None and backup_dir.exists():
            shutil.rmtree(backup_dir)

    return InstallResult(locked.version, str(runtime_dir), str(shim_path), True)


def self_check(reporter_binary: Path, expected_version: str) -> bool:
    """Run the installed binary's JSON status command without requiring pairing."""
    if not reporter_binary.is_file():
        return False
    try:
        reporter_home = reporter_binary.parents[4]
        environment = os.environ | {"SHOPOPS_REPORTER_HOME": str(reporter_home)}
        completed = subprocess.run(
            [str(reporter_binary), "--json", "status"],
            capture_output=True,
            check=False,
            env=environment,
            text=True,
            timeout=15,
        )
        payload = json.loads(completed.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, IndexError, TypeError):
        return False

    if (
        not isinstance(payload, dict)
        or payload.get("schema") != _REPORTER_SCHEMA
        or payload.get("reporter_version") != expected_version
        or payload.get("action") != "status"
        or not isinstance(payload.get("ok"), bool)
    ):
        return False
    if completed.returncode == 0:
        return (
            payload["ok"] is True
            and isinstance(payload.get("data"), dict)
            and "error" not in payload
        )
    error = payload.get("error")
    return (
        completed.returncode == 2
        and payload["ok"] is False
        and "data" not in payload
        and isinstance(error, dict)
        and error.get("code") == "not_paired"
        and isinstance(error.get("message"), str)
    )


def _locked_wheelhouse(plugin_root: Path, probe: EnvironmentProbe) -> _LockedWheelhouse:
    if not probe.supported or probe.python_executable is None or probe.python_version is None:
        raise InstallError(f"unsupported_environment:{probe.reason or 'unknown'}")
    if (probe.os_name, probe.architecture) != ("Darwin", "arm64"):
        raise InstallError("unsupported_environment:unsupported_platform")
    if (
        probe.python_architecture is None
        or probe.python_platform is None
        or not is_arm64_compatible(probe.python_architecture, probe.python_platform)
    ):
        raise InstallError("unsupported_environment:unsupported_python")

    abi = _abi_for(probe.python_version)
    try:
        manifest = json.loads((plugin_root / "reporter-manifest.json").read_text(encoding="utf-8"))
        checksums = json.loads((plugin_root / "checksums.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InstallError("invalid_manifest") from error
    if not isinstance(manifest, dict) or not isinstance(manifest.get("wheelhouses"), list):
        raise InstallError("invalid_manifest")
    if not isinstance(checksums, dict):
        raise InstallError("invalid_checksum_inventory")

    entries = manifest["wheelhouses"]
    matches = [
        entry
        for entry in entries
        if isinstance(entry, dict)
        and entry.get("platform") == _PLATFORM
        and entry.get("python") == abi.removeprefix("cp")
    ]
    if len(matches) != 1:
        raise InstallError(f"missing_wheelhouse:{_PLATFORM}:{abi}")
    entry = matches[0]
    version = entry.get("reporter_version")
    files = entry.get("files")
    if not isinstance(version, str) or not _VERSION.fullmatch(version) or not isinstance(files, list):
        raise InstallError("invalid_manifest")

    directory = plugin_root / "wheelhouse" / _PLATFORM / abi
    _validate_wheels(directory, files, checksums, abi, version)
    return _LockedWheelhouse(version=version, directory=directory)


def _abi_for(python_version: str) -> str:
    pieces = python_version.split(".")
    if len(pieces) < 2 or not all(piece.isdigit() for piece in pieces[:2]):
        raise InstallError("invalid_python_version")
    abi = f"cp{pieces[0]}{pieces[1]}"
    if abi not in {"cp311", "cp312"}:
        raise InstallError("unsupported_environment:unsupported_python")
    return abi


def _validate_wheels(
    directory: Path, files: list[Any], checksums: dict[str, Any], abi: str, version: str
) -> None:
    if not directory.is_dir() or not files:
        raise InstallError("invalid_manifest")
    names = [item.get("name") for item in files if isinstance(item, dict)]
    if len(names) != len(files) or not all(isinstance(name, str) for name in names) or names != sorted(names):
        raise InstallError("invalid_manifest")
    expected_paths = {f"wheelhouse/{_PLATFORM}/{abi}/{name}" for name in names}
    prefix = f"wheelhouse/{_PLATFORM}/{abi}/"
    inventory_paths = {key for key in checksums if isinstance(key, str) and key.startswith(prefix)}
    if inventory_paths != expected_paths:
        raise InstallError("checksum_inventory_mismatch")
    actual = sorted(path for path in directory.iterdir() if path.is_file())
    if [path.name for path in actual] != names or any(path.suffix != ".whl" for path in actual):
        raise InstallError("filename_mismatch")
    if not any(name.startswith(f"shopops_reporter-{version}-") for name in names):
        raise InstallError("missing_reporter_wheel")

    for item, path in zip(files, actual):
        expected_digest = item.get("sha256")
        relative = f"wheelhouse/{_PLATFORM}/{abi}/{path.name}"
        if not isinstance(expected_digest, str) or checksums.get(relative) != expected_digest:
            raise InstallError(f"checksum_inventory_mismatch:{path.name}")
        if _sha256(path) != expected_digest:
            raise InstallError(f"checksum_mismatch:{path.name}")


def _create_venv(python_executable: str | None, venv: Path) -> None:
    if python_executable is None:
        raise InstallError("unsupported_environment:unsupported_python")
    try:
        completed = subprocess.run(
            [python_executable, "-m", "venv", str(venv)], capture_output=True, check=False, text=True
        )
    except OSError as error:
        raise InstallError("venv_creation_failed") from error
    if completed.returncode != 0:
        raise InstallError("venv_creation_failed")


def _install_offline(venv_python: Path, locked: _LockedWheelhouse) -> None:
    try:
        completed = subprocess.run(
            [
                str(venv_python),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--find-links",
                str(locked.directory),
                f"shopops-reporter=={locked.version}",
            ],
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError as error:
        raise InstallError("offline_install_failed") from error
    if completed.returncode != 0:
        raise InstallError("offline_install_failed")


def _ensure_shim(shim_path: Path, reporter_binary: Path) -> bool:
    content = f"#!/bin/sh\nexec {shlex.quote(str(reporter_binary))} \"$@\"\n"
    try:
        if shim_path.read_text(encoding="utf-8") == content and stat.S_IMODE(shim_path.stat().st_mode) == 0o700:
            return False
    except FileNotFoundError:
        pass

    shim_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".shopops-report.", dir=shim_path.parent, text=True)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        temporary.write_text(content, encoding="utf-8")
        temporary.chmod(0o700)
        os.replace(temporary, shim_path)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def _relocate_console_script(reporter_binary: Path) -> None:
    """Write a shell-safe final launcher after moving a staged venv."""
    python = reporter_binary.parent / "python"
    if not python.is_file():
        raise InstallError("missing_reporter_binary")
    launcher = f"#!/bin/sh\nexec {shlex.quote(str(python))} -m shopops_reporter \"$@\"\n"
    reporter_binary.write_text(launcher, encoding="utf-8")
    reporter_binary.chmod(0o700)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()
