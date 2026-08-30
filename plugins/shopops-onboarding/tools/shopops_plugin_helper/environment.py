"""Deterministically inspect whether this machine can install ShopOps Reporter."""

from __future__ import annotations

from dataclasses import dataclass
import json
import platform
import subprocess
import sys
from collections.abc import Sequence


_VERSION_QUERY = (
    "import json, sys; "
    "print(json.dumps({'implementation': sys.implementation.name, "
    "'version_info': list(sys.version_info[:3])}))"
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
            supported=False,
            reason="unsupported_platform",
        )

    for candidate in _DEFAULT_CANDIDATES if candidates is None else candidates:
        version = _read_python_version(candidate)
        if version is None:
            continue

        implementation, version_info = version
        if implementation == "cpython" and version_info[:2] in _SUPPORTED_VERSIONS:
            return EnvironmentProbe(
                os_name=os_name,
                architecture=architecture,
                python_executable=candidate,
                python_version=".".join(str(part) for part in version_info),
                supported=True,
                reason=None,
            )

    return EnvironmentProbe(
        os_name=os_name,
        architecture=architecture,
        python_executable=None,
        python_version=None,
        supported=False,
        reason="unsupported_python",
    )


def _read_python_version(candidate: str) -> tuple[str, tuple[int, int, int]] | None:
    """Ask an interpreter for its implementation and semantic version."""
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
        if (
            not isinstance(implementation, str)
            or not isinstance(raw_version, list)
            or len(raw_version) != 3
            or not all(isinstance(part, int) for part in raw_version)
        ):
            return None
    except (json.JSONDecodeError, KeyError, TypeError):
        return None

    return implementation, tuple(raw_version)
