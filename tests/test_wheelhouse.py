import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
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
    for platform_name, abi in wheelhouse_writer.SUPPORTED_WHEELHOUSES:
        directory = plugin_root / "wheelhouse" / platform_name / abi
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


def release_stage(plugin_root: Path, tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    release_root = tmp_path / "release"
    staged_platform = release_root / "macos-arm64"
    shutil.copytree(plugin_root / "wheelhouse" / "macos-arm64", staged_platform)
    staged_manifest = release_root / "reporter-manifest.json"
    staged_checksums = release_root / "checksums.json"
    shutil.copy2(plugin_root / "reporter-manifest.json", staged_manifest)
    shutil.copy2(plugin_root / "checksums.json", staged_checksums)
    return release_root, staged_platform, staged_manifest, staged_checksums


def plugin_snapshot(plugin_root: Path) -> dict[str, bytes]:
    paths = [
        plugin_root / "wheelhouse" / "macos-arm64",
        plugin_root / "reporter-manifest.json",
        plugin_root / "checksums.json",
    ]
    snapshot = {}
    for path in paths:
        if path.is_dir():
            snapshot.update(
                {
                    str(child.relative_to(plugin_root)): child.read_bytes()
                    for child in path.rglob("*")
                    if child.is_file()
                }
            )
        elif path.is_file():
            snapshot[str(path.relative_to(plugin_root))] = path.read_bytes()
    return snapshot


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


@pytest.mark.parametrize("manifest", [{}, {"wheelhouses": []}])
def test_invalid_or_empty_manifest_never_bootstraps_an_unlocked_rebuild(tmp_path, manifest):
    """Catch syntactically valid but unusable locks before network resolution."""
    plugin_root = fake_plugin_root(tmp_path)
    (plugin_root / "reporter-manifest.json").write_text(json.dumps(manifest))

    with pytest.raises(wheelhouse_writer.LockValidationError):
        wheelhouse_writer.locked_requirements(plugin_root, "macos-arm64", "cp311", "0.1.0")


def test_current_version_missing_an_abi_never_bootstraps_an_unlocked_rebuild(tmp_path):
    """Catch a partial current-version matrix even when the requested ABI looks valid."""
    plugin_root = fake_plugin_root(tmp_path)
    manifest_path = plugin_root / "reporter-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["wheelhouses"] = [entry for entry in manifest["wheelhouses"] if entry["python"] == "311"]
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(wheelhouse_writer.LockValidationError, match="missing_required_abi"):
        wheelhouse_writer.locked_requirements(plugin_root, "macos-arm64", "cp311", "0.1.0")


def test_different_reporter_version_manifest_may_bootstrap_a_new_lock(tmp_path):
    """Allow a genuine version bump rather than failing on a valid previous release."""
    plugin_root = fake_plugin_root(tmp_path)
    manifest_path = plugin_root / "reporter-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["wheelhouses"]:
        entry["reporter_version"] = "0.2.0"
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(wheelhouse_writer.LockUnavailable):
        wheelhouse_writer.locked_requirements(plugin_root, "macos-arm64", "cp311", "0.1.0")


def test_absent_manifest_may_bootstrap_a_new_lock(tmp_path):
    """Allow first release construction when no committed lock exists at all."""
    plugin_root = fake_plugin_root(tmp_path)
    (plugin_root / "reporter-manifest.json").unlink()

    with pytest.raises(wheelhouse_writer.LockUnavailable):
        wheelhouse_writer.locked_requirements(plugin_root, "macos-arm64", "cp311", "0.1.0")


def test_clean_bootstrap_without_manifest_or_checksums_may_create_a_new_lock(tmp_path):
    """Allow a first build before either committed metadata file exists."""
    plugin_root = fake_plugin_root(tmp_path)
    (plugin_root / "reporter-manifest.json").unlink()
    (plugin_root / "checksums.json").unlink()

    with pytest.raises(wheelhouse_writer.LockUnavailable):
        wheelhouse_writer.locked_requirements(plugin_root, "macos-arm64", "cp311", "0.1.0")


def test_duplicate_current_version_entries_never_bootstrap_an_unlocked_rebuild(tmp_path):
    """Catch ambiguous same-version locks before a resolver can choose one arbitrarily."""
    plugin_root = fake_plugin_root(tmp_path)
    manifest_path = plugin_root / "reporter-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["wheelhouses"].append(manifest["wheelhouses"][0])
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(wheelhouse_writer.LockValidationError, match="duplicate_lock_entries"):
        wheelhouse_writer.locked_requirements(plugin_root, "macos-arm64", "cp311", "0.1.0")


def test_same_version_lock_rejects_an_extra_checksum_for_its_abi_prefix(tmp_path):
    """Catch a checksum inventory that names an artifact absent from the signed file list."""
    plugin_root = fake_plugin_root(tmp_path)
    checksums_path = plugin_root / "checksums.json"
    checksums = json.loads(checksums_path.read_text())
    checksums["wheelhouse/macos-arm64/cp311/unexpected-1.0-py3-none-any.whl"] = "1" * 64
    checksums_path.write_text(json.dumps(checksums))

    with pytest.raises(wheelhouse_writer.LockValidationError, match="checksum_inventory_extra"):
        wheelhouse_writer.locked_requirements(plugin_root, "macos-arm64", "cp311", "0.1.0")


def test_same_version_lock_preserves_other_platform_checksum_inventory(tmp_path):
    """Keep future platform entries out of the macOS ABI-specific inventory check."""
    plugin_root = fake_plugin_root(tmp_path)
    checksums_path = plugin_root / "checksums.json"
    checksums = json.loads(checksums_path.read_text())
    checksums["wheelhouse/windows-x64/cp311/future-1.0-py3-none-any.whl"] = "2" * 64
    checksums_path.write_text(json.dumps(checksums))

    assert wheelhouse_writer.locked_requirements(plugin_root, "macos-arm64", "cp311", "0.1.0")


def test_manifest_writer_records_each_platform_reporter_version(tmp_path):
    plugin_root = fake_plugin_root(tmp_path)
    windows_wheel = (
        plugin_root
        / "wheelhouse/windows-x64/cp311/shopops_reporter-0.1.0-py3-none-any.whl"
    )
    windows_wheel.unlink()
    write_test_wheel(
        windows_wheel.with_name("shopops_reporter-0.2.0-py3-none-any.whl"),
        "shopops-reporter",
        "0.2.0",
        ("dependency>=1",),
    )

    wheelhouse_writer.write_manifests(plugin_root, "0.2.0")

    manifest = json.loads((plugin_root / "reporter-manifest.json").read_text())
    versions = {
        (entry["platform"], entry["python"]): entry["reporter_version"]
        for entry in manifest["wheelhouses"]
    }
    assert versions[("macos-arm64", "311")] == "0.1.0"
    assert versions[("windows-x64", "311")] == "0.2.0"


def test_promotion_creates_clean_bootstrap_parents(tmp_path):
    """Catch a clean install path that assumes wheelhouse parents already exist."""
    source_root = fake_plugin_root(tmp_path / "source")
    plugin_root = tmp_path / "bootstrap" / "plugin"
    release_root, staged_platform, staged_manifest, staged_checksums = release_stage(source_root, tmp_path / "stage")

    wheelhouse_writer.promote_release(
        plugin_root, staged_platform, staged_manifest, staged_checksums, release_root / "backup"
    )

    assert (plugin_root / "wheelhouse" / "macos-arm64" / "cp311").is_dir()
    assert (plugin_root / "reporter-manifest.json").is_file()
    assert (plugin_root / "checksums.json").is_file()


@pytest.mark.parametrize("failure_call", range(1, 7))
def test_promotion_rolls_back_every_replacement_failure(tmp_path, failure_call):
    """Catch any partial replacement that leaves wheelhouse or metadata mixed across releases."""
    plugin_root = fake_plugin_root(tmp_path / "plugin")
    release_root, staged_platform, staged_manifest, staged_checksums = release_stage(plugin_root, tmp_path / "stage")
    before = plugin_snapshot(plugin_root)
    calls = 0

    def fail_once(source: str | Path, destination: str | Path) -> None:
        nonlocal calls
        calls += 1
        if calls == failure_call:
            raise OSError(f"injected replacement failure {failure_call}")
        os.replace(source, destination)

    with pytest.raises(OSError, match="injected replacement failure"):
        wheelhouse_writer.promote_release(
            plugin_root,
            staged_platform,
            staged_manifest,
            staged_checksums,
            release_root / "backup",
            replace=fail_once,
        )

    assert plugin_snapshot(plugin_root) == before


@pytest.mark.parametrize(
    ("platform_name", "abi"),
    [(platform_name, abi) for platform_name, abi in wheelhouse_writer.SUPPORTED_WHEELHOUSES],
)
def test_wheelhouse_contains_reporter_and_verified_dependencies(platform_name, abi):
    """Catch a missing, altered, or source-only artifact before offline installation."""
    files = manifest_files(platform_name, abi)

    assert files
    assert list(files) == sorted(files)
    assert any(name.startswith("shopops_reporter-0.3.0-") for name in files)
    assert all(name.endswith(".whl") for name in files)
    assert all(path.is_file() and sha256(path) == expected for path, expected in files.values())


@pytest.mark.parametrize(
    ("platform_name", "abi"),
    [(platform_name, abi) for platform_name, abi in wheelhouse_writer.SUPPORTED_WHEELHOUSES],
)
def test_checksums_inventory_matches_manifest_and_wheelhouse(platform_name, abi):
    """Catch drift between the install manifest, checksum inventory, and payload."""
    checksums = json.loads((PLUGIN_ROOT / "checksums.json").read_text())
    files = manifest_files(platform_name, abi)
    relative_paths = {
        f"wheelhouse/{platform_name}/{abi}/{name}": expected
        for name, (_, expected) in files.items()
    }

    assert {key: checksums[key] for key in relative_paths} == relative_paths
    assert sorted(checksums) == list(checksums)
    assert set(path.name for path in (WHEELHOUSE_ROOT / platform_name / abi).iterdir()) == set(files)


@pytest.mark.parametrize(
    ("platform_name", "abi"),
    [(platform_name, abi) for platform_name, abi in wheelhouse_writer.SUPPORTED_WHEELHOUSES],
)
def test_wheelhouse_has_every_active_runtime_dependency(platform_name, abi):
    """Catch a conditional or transitive dependency absent from an offline install."""
    files = manifest_files(platform_name, abi)
    wheels = [path for path, _ in files.values()]
    available = {wheel_name(path): wheel_version(path) for path in wheels}
    environment = default_environment()
    environment.update(
        {
            "implementation_name": "cpython",
            "platform_machine": "arm64" if platform_name == "macos-arm64" else "AMD64",
            "platform_python_implementation": "CPython",
            "platform_system": "Darwin" if platform_name == "macos-arm64" else "Windows",
            "python_full_version": f"{abi[2]}.{abi[3:]}.0",
            "python_version": f"{abi[2]}.{abi[3:]}",
            "sys_platform": "darwin" if platform_name == "macos-arm64" else "win32",
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
