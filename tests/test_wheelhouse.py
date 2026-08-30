import hashlib
import importlib.util
import json
from pathlib import Path
from zipfile import ZipFile

import pytest
from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.version import Version


PLUGIN_ROOT = Path("plugins/shopops-onboarding")
WHEELHOUSE_ROOT = PLUGIN_ROOT / "wheelhouse"
WRITER_SPEC = importlib.util.spec_from_file_location(
    "wheelhouse_writer", Path("scripts/write_checksums.py")
)
assert WRITER_SPEC and WRITER_SPEC.loader
wheelhouse_writer = importlib.util.module_from_spec(WRITER_SPEC)
WRITER_SPEC.loader.exec_module(wheelhouse_writer)


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


def wheel_version(path: Path) -> Version:
    with ZipFile(path) as wheel:
        metadata_path = next(name for name in wheel.namelist() if name.endswith(".dist-info/METADATA"))
        for line in wheel.read(metadata_path).decode().splitlines():
            if line.startswith("Version: "):
                return Version(line.removeprefix("Version: "))
    raise AssertionError(f"wheel metadata has no Version field: {path}")


def wheel_requirements(path: Path) -> list[Requirement]:
    with ZipFile(path) as wheel:
        metadata_path = next(name for name in wheel.namelist() if name.endswith(".dist-info/METADATA"))
        return [
            Requirement(line.removeprefix("Requires-Dist: "))
            for line in wheel.read(metadata_path).decode().splitlines()
            if line.startswith("Requires-Dist: ")
        ]


def write_test_wheel(
    path: Path, name: str, version: str, requirements: tuple[str, ...] = (), payload: bytes = b"valid"
) -> None:
    metadata = "\n".join(
        [f"Name: {name}", f"Version: {version}", *(f"Requires-Dist: {item}" for item in requirements)]
    )
    with ZipFile(path, "w") as wheel:
        wheel.writestr(f"{name.replace('-', '_')}-{version}.dist-info/METADATA", metadata)
        wheel.writestr(f"{name.replace('-', '_')}/payload.txt", payload)


def fake_plugin_root(tmp_path: Path) -> Path:
    plugin_root = tmp_path / "plugin"
    for abi in ("cp311", "cp312"):
        directory = plugin_root / "wheelhouse" / "macos-arm64" / abi
        directory.mkdir(parents=True)
        write_test_wheel(
            directory / "shopops_reporter-0.1.0-py3-none-any.whl",
            "shopops-reporter",
            "0.1.0",
            ("dependency>=1",),
        )
        write_test_wheel(directory / "dependency-1.0-py3-none-any.whl", "dependency", "1.0")
    wheelhouse_writer.write_manifests(plugin_root, "0.1.0")
    return plugin_root


def file_bytes(directory: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in sorted(directory.iterdir())}


def test_same_version_lock_rejects_a_tampered_committed_wheel(tmp_path):
    """Catch a live payload whose bytes no longer match its committed manifest hash."""
    plugin_root = fake_plugin_root(tmp_path)
    wheel = plugin_root / "wheelhouse/macos-arm64/cp311/dependency-1.0-py3-none-any.whl"
    wheel.write_bytes(wheel.read_bytes() + b"tampered")

    with pytest.raises(wheelhouse_writer.LockValidationError, match="checksum_mismatch"):
        wheelhouse_writer.locked_requirements(plugin_root, "macos-arm64", "cp311", "0.1.0")


def test_same_version_lock_rejects_an_altered_checksum_inventory(tmp_path):
    """Catch a manifest/checksums disagreement before any rebuild can consume it."""
    plugin_root = fake_plugin_root(tmp_path)
    checksums_path = plugin_root / "checksums.json"
    checksums = json.loads(checksums_path.read_text())
    checksums["wheelhouse/macos-arm64/cp311/dependency-1.0-py3-none-any.whl"] = "0" * 64
    checksums_path.write_text(json.dumps(checksums))

    with pytest.raises(wheelhouse_writer.LockValidationError, match="checksum_inventory_mismatch"):
        wheelhouse_writer.locked_requirements(plugin_root, "macos-arm64", "cp311", "0.1.0")


def test_same_version_lock_emits_exact_hash_pinned_requirements(tmp_path):
    """Catch a rebuild input that pins a version but not its committed artifact bytes."""
    plugin_root = fake_plugin_root(tmp_path)
    dependency = plugin_root / "wheelhouse/macos-arm64/cp311/dependency-1.0-py3-none-any.whl"

    assert wheelhouse_writer.locked_requirements(
        plugin_root, "macos-arm64", "cp311", "0.1.0"
    ) == [f"dependency==1.0 --hash=sha256:{sha256(dependency)}"]


def test_same_version_rebuild_rejects_changed_reporter_and_preserves_live_payload(tmp_path):
    """Catch an unversioned Reporter source change without touching the live wheelhouse."""
    plugin_root = fake_plugin_root(tmp_path)
    live = plugin_root / "wheelhouse/macos-arm64/cp311"
    staged = tmp_path / "staged"
    staged.mkdir()
    for path in live.iterdir():
        (staged / path.name).write_bytes(path.read_bytes())
    write_test_wheel(
        staged / "shopops_reporter-0.1.0-py3-none-any.whl",
        "shopops-reporter",
        "0.1.0",
        ("dependency>=1",),
        payload=b"changed source without version bump",
    )
    before = file_bytes(live)

    with pytest.raises(wheelhouse_writer.LockValidationError, match="checksum_mismatch"):
        wheelhouse_writer.validate_locked_wheelhouse(
            plugin_root, "macos-arm64", "cp311", "0.1.0", staged
        )

    assert file_bytes(live) == before


def test_new_reporter_version_has_no_same_version_lock(tmp_path):
    """Allow a version bump to create a new lock instead of borrowing the old one."""
    plugin_root = fake_plugin_root(tmp_path)

    with pytest.raises(wheelhouse_writer.LockUnavailable):
        wheelhouse_writer.locked_requirements(plugin_root, "macos-arm64", "cp311", "0.2.0")


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
    available = {wheel_name(path): wheel_version(path) for path in wheels}
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

    unsatisfied = {
        str(requirement): available.get(requirement.name.lower().replace("-", "_"))
        for wheel in wheels
        for requirement in wheel_requirements(wheel)
        if requirement.marker is None or requirement.marker.evaluate(environment)
        if requirement.name.lower().replace("-", "_") not in available
        or not requirement.specifier.contains(
            available[requirement.name.lower().replace("-", "_")], prereleases=True
        )
    }
    assert not unsatisfied
