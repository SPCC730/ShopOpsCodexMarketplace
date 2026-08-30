import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import pytest
from packaging.markers import default_environment
from packaging.requirements import Requirement


PLUGIN_ROOT = Path("plugins/shopops-onboarding")
WHEELHOUSE_ROOT = PLUGIN_ROOT / "wheelhouse"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_files(platform: str, abi: str) -> dict[str, tuple[Path, str]]:
    manifest = json.loads((PLUGIN_ROOT / "reporter-manifest.json").read_text())
    entry = next(
        item
        for item in manifest["wheelhouses"]
        if item["platform"] == platform and item["python"] == abi.removeprefix("cp")
    )
    return {
        item["name"]: (WHEELHOUSE_ROOT / platform / abi / item["name"], item["sha256"])
        for item in entry["files"]
    }


def wheel_name(path: Path) -> str:
    with ZipFile(path) as wheel:
        metadata_path = next(name for name in wheel.namelist() if name.endswith(".dist-info/METADATA"))
        for line in wheel.read(metadata_path).decode().splitlines():
            if line.startswith("Name: "):
                return line.removeprefix("Name: ").lower().replace("-", "_")
    raise AssertionError(f"wheel metadata has no Name field: {path}")


def wheel_requirements(path: Path) -> list[Requirement]:
    with ZipFile(path) as wheel:
        metadata_path = next(name for name in wheel.namelist() if name.endswith(".dist-info/METADATA"))
        return [
            Requirement(line.removeprefix("Requires-Dist: "))
            for line in wheel.read(metadata_path).decode().splitlines()
            if line.startswith("Requires-Dist: ")
        ]


@pytest.mark.parametrize("abi", ["cp311", "cp312"])
def test_wheelhouse_contains_reporter_and_verified_dependencies(abi):
    """Catch a missing, altered, or source-only artifact before offline installation."""
    files = manifest_files("macos-arm64", abi)

    assert files
    assert list(files) == sorted(files)
    assert any(name.startswith("shopops_reporter-0.1.0-") for name in files)
    assert all(name.endswith(".whl") for name in files)
    assert all(path.is_file() and sha256(path) == expected for path, expected in files.values())


@pytest.mark.parametrize("abi", ["cp311", "cp312"])
def test_checksums_inventory_matches_manifest_and_wheelhouse(abi):
    """Catch drift between the install manifest, checksum inventory, and payload."""
    checksums = json.loads((PLUGIN_ROOT / "checksums.json").read_text())
    files = manifest_files("macos-arm64", abi)
    relative_paths = {
        f"wheelhouse/macos-arm64/{abi}/{name}": expected
        for name, (_, expected) in files.items()
    }

    assert {key: checksums[key] for key in relative_paths} == relative_paths
    assert sorted(checksums) == list(checksums)
    assert set(path.name for path in (WHEELHOUSE_ROOT / "macos-arm64" / abi).iterdir()) == set(files)


@pytest.mark.parametrize("abi", ["cp311", "cp312"])
def test_wheelhouse_has_every_active_runtime_dependency(abi):
    """Catch a conditional or transitive dependency absent from an offline install."""
    files = manifest_files("macos-arm64", abi)
    wheels = [path for path, _ in files.values()]
    available = {wheel_name(path) for path in wheels}
    environment = default_environment()
    environment.update(
        {
            "implementation_name": "cpython",
            "platform_machine": "arm64",
            "platform_python_implementation": "CPython",
            "platform_system": "Darwin",
            "python_full_version": f"{abi[2]}.{abi[3:]}.0",
            "python_version": f"{abi[2]}.{abi[3:]}",
            "sys_platform": "darwin",
        }
    )

    required = {
        requirement.name.lower().replace("-", "_")
        for wheel in wheels
        for requirement in wheel_requirements(wheel)
        if requirement.marker is None or requirement.marker.evaluate(environment)
    }
    assert required <= available
