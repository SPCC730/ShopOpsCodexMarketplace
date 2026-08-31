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
    "'python_platform': sysconfig.get_platform()}))"
)
_DEFAULT_CANDIDATES = ("python3.12", "python3.11", sys.executable)
_SUPPORTED_VERSIONS = {(3, 11), (3, 12)}


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


def probe_environment(candidates: Sequence[str] | None = None) -> EnvironmentProbe:
    """Return installation support using only the declared interpreter candidates."""
    os_name = platform.system()
    architecture = platform.machine()
    if (os_name, architecture) != ("Darwin", "arm64"):
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

    for candidate in _DEFAULT_CANDIDATES if candidates is None else candidates:
        details = _read_python_details(candidate)
        if details is None:
            continue

        implementation, version_info, python_architecture, python_platform = details
        if (
            implementation == "cpython"
            and version_info[:2] in _SUPPORTED_VERSIONS
            and is_arm64_compatible(python_architecture, python_platform)
        ):
            return EnvironmentProbe(
                os_name=os_name,
                architecture=architecture,
                python_executable=candidate,
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


def _read_python_details(
    candidate: str,
) -> tuple[str, tuple[int, int, int], str, str] | None:
    """Ask an interpreter for its implementation, version, and compatible platform."""
    try:
        completed = subprocess.run(
            [candidate, "-c", _VERSION_QUERY],
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
        ):
            return None
    except (json.JSONDecodeError, KeyError, TypeError):
        return None

    return implementation, tuple(raw_version), python_architecture, python_platform
