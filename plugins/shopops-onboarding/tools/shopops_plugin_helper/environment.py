"""Deterministically inspect whether this machine can install ShopOps Reporter."""

from __future__ import annotations

from dataclasses import dataclass
import json
import platform
import subprocess
import sys
from collections.abc import Sequence


_VERSION_QUERY = (
    "import json, platform, sys, sysconfig; "
    "print(json.dumps({'implementation': sys.implementation.name, "
    "'version_info': list(sys.version_info[:3]), "
    "'python_architecture': platform.machine(), "
    "'python_platform': sysconfig.get_platform(), "
    "'python_executable': sys.executable}))"
)
_SUPPORTED_VERSIONS = {(3, 11), (3, 12)}
_WINDOWS_X64_ARCHITECTURES = {"amd64", "x86_64"}


@dataclass(frozen=True)
class EnvironmentProbe:
    """Result of evaluating the platform and an available Python interpreter."""

    os_name: str
    architecture: str
    python_executable: str | None
    python_version: str | None
    python_architecture: str | None
    python_platform: str | None
    supported: bool
    reason: str | None


def probe_environment(candidates: Sequence[str | Sequence[str]] | None = None) -> EnvironmentProbe:
    """Return installation support using only the declared interpreter candidates."""
    os_name = platform.system()
    architecture = platform.machine()
    if platform_key(os_name, architecture) is None:
        return EnvironmentProbe(
            os_name=os_name,
            architecture=architecture,
            python_executable=None,
            python_version=None,
            python_architecture=None,
            python_platform=None,
            supported=False,
            reason="unsupported_platform",
        )

    selected_candidates = _default_candidates(os_name) if candidates is None else candidates
    for candidate in selected_candidates:
        details = _read_python_details(candidate)
        if details is None:
            continue

        implementation, version_info, python_architecture, python_platform, python_executable = details
        if (
            implementation == "cpython"
            and version_info[:2] in _SUPPORTED_VERSIONS
            and is_interpreter_compatible(
                os_name,
                architecture,
                python_architecture,
                python_platform,
            )
        ):
            return EnvironmentProbe(
                os_name=os_name,
                architecture=architecture,
                python_executable=python_executable,
                python_version=".".join(str(part) for part in version_info),
                python_architecture=python_architecture,
                python_platform=python_platform,
                supported=True,
                reason=None,
            )

    return EnvironmentProbe(
        os_name=os_name,
        architecture=architecture,
        python_executable=None,
        python_version=None,
        python_architecture=None,
        python_platform=None,
        supported=False,
        reason="unsupported_python",
    )


def is_arm64_compatible(architecture: str, platform_tag: str) -> bool:
    """Return whether an interpreter can consume the vendored macOS arm64 wheels."""
    return (
        architecture.lower() == "arm64"
        and platform_tag.lower().startswith("macosx-")
        and platform_tag.lower().rsplit("-", 1)[-1] in {"arm64", "universal2"}
    )


def platform_key(os_name: str, architecture: str) -> str | None:
    """Map a supported host to its locked wheelhouse key."""
    normalized_architecture = architecture.lower()
    if os_name == "Darwin" and normalized_architecture == "arm64":
        return "macos-arm64"
    if os_name == "Windows" and normalized_architecture in _WINDOWS_X64_ARCHITECTURES:
        return "windows-x64"
    return None


def is_interpreter_compatible(
    os_name: str,
    host_architecture: str,
    python_architecture: str,
    platform_tag: str,
) -> bool:
    """Return whether an interpreter can consume its host's locked wheels."""
    selected_platform = platform_key(os_name, host_architecture)
    if selected_platform == "macos-arm64":
        return is_arm64_compatible(python_architecture, platform_tag)
    if selected_platform == "windows-x64":
        return (
            python_architecture.lower() in _WINDOWS_X64_ARCHITECTURES
            and platform_tag.lower() in {"win-amd64", "win_amd64"}
        )
    return False


def _default_candidates(os_name: str) -> tuple[str | tuple[str, ...], ...]:
    if os_name == "Windows":
        return (
            ("py", "-3.12"),
            ("py", "-3.11"),
            "python3.12",
            "python3.11",
            sys.executable,
        )
    return ("python3.12", "python3.11", sys.executable)


def _read_python_details(
    candidate: str | Sequence[str],
) -> tuple[str, tuple[int, int, int], str, str, str] | None:
    """Ask an interpreter for its implementation, version, and compatible platform."""
    try:
        command = [candidate] if isinstance(candidate, str) else list(candidate)
        completed = subprocess.run(
            [*command, "-c", _VERSION_QUERY],
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if completed.returncode != 0:
        return None

    try:
        payload = json.loads(completed.stdout)
        implementation = payload["implementation"]
        raw_version = payload["version_info"]
        python_architecture = payload["python_architecture"]
        python_platform = payload["python_platform"]
        python_executable = payload.get("python_executable")
        if python_executable is None and isinstance(candidate, str):
            python_executable = candidate
        if (
            not isinstance(implementation, str)
            or not implementation
            or not isinstance(raw_version, list)
            or len(raw_version) != 3
            or not all(
                isinstance(part, int) and not isinstance(part, bool) and part >= 0
                for part in raw_version
            )
            or not isinstance(python_architecture, str)
            or not python_architecture
            or not isinstance(python_platform, str)
            or not python_platform
            or not isinstance(python_executable, str)
            or not python_executable
        ):
            return None
    except (json.JSONDecodeError, KeyError, TypeError):
        return None

    return implementation, tuple(raw_version), python_architecture, python_platform, python_executable
