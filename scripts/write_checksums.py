#!/usr/bin/env python3
"""Write and validate deterministic Reporter wheelhouse manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from email.parser import BytesParser
from pathlib import Path
from zipfile import ZipFile


SUPPORTED_WHEELHOUSES = (
    ("macos-arm64", "cp311"),
    ("macos-arm64", "cp312"),
    ("windows-x64", "cp311"),
    ("windows-x64", "cp312"),
)


class LockUnavailable(Exception):
    """A different Reporter version needs a newly resolved wheelhouse lock."""


class LockValidationError(Exception):
    """A same-version wheelhouse differs from its committed lock."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def wheel_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        raise ValueError(f"wheelhouse is missing: {directory}")
    files = sorted(path for path in directory.iterdir() if path.is_file())
    if not files:
        raise ValueError(f"wheelhouse is empty: {directory}")
    if any(path.suffix != ".whl" for path in files):
        raise ValueError(f"source distributions are not allowed: {directory}")
    return files


def wheel_metadata(path: Path) -> tuple[str, str]:
    with ZipFile(path) as wheel:
        metadata_path = next(name for name in wheel.namelist() if name.endswith(".dist-info/METADATA"))
        metadata = BytesParser().parsebytes(wheel.read(metadata_path))
    name = metadata["Name"]
    version = metadata["Version"]
    if not name or not version:
        raise LockValidationError(f"wheel_metadata_incomplete:{path.name}")
    return name, version


def _valid_entries(
    manifest_path: Path,
) -> list[dict[str, object]]:
    if not manifest_path.exists():
        raise LockUnavailable("no_committed_lock")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise LockValidationError("invalid_committed_lock") from error
    if not isinstance(manifest, dict):
        raise LockValidationError("invalid_manifest")
    entries = manifest.get("wheelhouses")
    if not isinstance(entries, list) or not entries:
        raise LockValidationError("invalid_wheelhouses")
    if not all(isinstance(entry, dict) for entry in entries):
        raise LockValidationError("invalid_wheelhouse_entry")
    for entry in entries:
        if not all(isinstance(entry.get(key), str) for key in ("platform", "python", "reporter_version")):
            raise LockValidationError("invalid_wheelhouse_entry")
        if not isinstance(entry.get("files"), list):
            raise LockValidationError("invalid_wheelhouse_entry")
    return entries


def _matching_entry(
    entries: list[dict[str, object]], platform: str, abi: str, reporter_version: str
) -> dict[str, object]:
    seen = set()
    for entry in entries:
        key = (entry["platform"], entry["python"], entry["reporter_version"])
        if key in seen:
            raise LockValidationError(f"duplicate_lock_entries:{key[0]}:{key[1]}:{key[2]}")
        seen.add(key)

    current_version_entries = [entry for entry in entries if entry["reporter_version"] == reporter_version]
    if not current_version_entries:
        raise LockUnavailable(f"no_same_version_lock:{platform}:{abi}:{reporter_version}")
    platform_entries = [entry for entry in current_version_entries if entry["platform"] == platform]
    if not platform_entries:
        raise LockUnavailable(f"no_platform_lock:{platform}:{reporter_version}")
    for required_abi in ("cp311", "cp312"):
        required_python = required_abi.removeprefix("cp")
        if not any(entry["python"] == required_python for entry in platform_entries):
            raise LockValidationError(
                f"missing_required_abi:{platform}:{required_abi}:{reporter_version}"
            )

    matches = [entry for entry in platform_entries if entry["python"] == abi.removeprefix("cp")]
    if len(matches) != 1:
        raise LockValidationError(f"invalid_required_abi:{platform}:{abi}:{reporter_version}")
    return matches[0]


def validate_locked_wheelhouse(
    plugin_root: Path,
    platform: str,
    abi: str,
    reporter_version: str,
    candidate_directory: Path,
) -> list[Path]:
    """Validate an exact staged/live wheel set against the committed same-version lock."""
    manifest_path = plugin_root / "reporter-manifest.json"
    checksums_path = plugin_root / "checksums.json"
    entries = _valid_entries(manifest_path)
    try:
        checksums = json.loads(checksums_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise LockValidationError("invalid_committed_lock") from error
    if not isinstance(checksums, dict):
        raise LockValidationError("invalid_checksum_inventory")

    entry = _matching_entry(entries, platform, abi, reporter_version)
    expected = entry.get("files")
    if not isinstance(expected, list):
        raise LockValidationError("invalid_manifest_files")
    expected_names = [item.get("name") for item in expected if isinstance(item, dict)]
    if len(expected_names) != len(expected) or expected_names != sorted(expected_names):
        raise LockValidationError("invalid_manifest_file_order")

    try:
        actual = wheel_files(candidate_directory)
    except ValueError as error:
        raise LockValidationError(str(error)) from error
    if [path.name for path in actual] != expected_names:
        raise LockValidationError("filename_mismatch")

    expected_paths = {
        f"wheelhouse/{platform}/{abi}/{item['name']}"
        for item in expected
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    prefix = f"wheelhouse/{platform}/{abi}/"
    inventory_paths = {key for key in checksums if key.startswith(prefix)}
    if inventory_paths - expected_paths:
        raise LockValidationError(f"checksum_inventory_extra:{platform}:{abi}")
    if expected_paths - inventory_paths:
        raise LockValidationError(f"checksum_inventory_missing:{platform}:{abi}")

    for item, path in zip(expected, actual, strict=True):
        expected_digest = item.get("sha256")
        relative = f"wheelhouse/{platform}/{abi}/{path.name}"
        if checksums.get(relative) != expected_digest:
            raise LockValidationError(f"checksum_inventory_mismatch:{path.name}")
        if sha256(path) != expected_digest:
            raise LockValidationError(f"checksum_mismatch:{path.name}")
    return actual


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def promote_release(
    plugin_root: Path,
    staged_platform_root: Path,
    staged_manifest: Path,
    staged_checksums: Path,
    backup_root: Path,
    replace=os.replace,
) -> None:
    """Replace wheelhouse and metadata together, restoring prior bytes on any failure."""
    platform = staged_platform_root.name
    live_platform_root = plugin_root / "wheelhouse" / platform
    live_manifest = plugin_root / "reporter-manifest.json"
    live_checksums = plugin_root / "checksums.json"
    live_platform_root.parent.mkdir(parents=True, exist_ok=True)
    backup_root.mkdir(parents=True, exist_ok=True)
    targets = (
        (staged_platform_root, live_platform_root, backup_root / platform),
        (staged_manifest, live_manifest, backup_root / "reporter-manifest.json"),
        (staged_checksums, live_checksums, backup_root / "checksums.json"),
    )
    records: list[tuple[Path, Path, bool, bool]] = []
    try:
        for staged, live, backup in targets:
            had_previous = live.exists()
            moved_previous = False
            moved_staged = False
            records.append((live, backup, moved_previous, moved_staged))
            if had_previous:
                replace(live, backup)
                moved_previous = True
                records[-1] = (live, backup, moved_previous, moved_staged)
            replace(staged, live)
            moved_staged = True
            records[-1] = (live, backup, moved_previous, moved_staged)
    except Exception:
        for live, backup, moved_previous, moved_staged in reversed(records):
            if moved_staged:
                _remove_path(live)
            if moved_previous:
                replace(backup, live)
        raise


def locked_requirements(
    plugin_root: Path, platform: str, abi: str, reporter_version: str
) -> list[str]:
    """Return pip-compatible, hash-pinned dependency requirements for a verified lock."""
    directory = plugin_root / "wheelhouse" / platform / abi
    files = validate_locked_wheelhouse(plugin_root, platform, abi, reporter_version, directory)
    requirements = []
    for path in files:
        name, version = wheel_metadata(path)
        if name.lower().replace("-", "_") != "shopops_reporter":
            requirements.append(f"{name}=={version} --hash=sha256:{sha256(path)}")
    return sorted(requirements)


def write_manifests(
    plugin_root: Path,
    reporter_version: str,
    wheelhouse_root: Path | None = None,
    manifest_output: Path | None = None,
    checksums_output: Path | None = None,
) -> None:
    wheelhouse_root = wheelhouse_root or plugin_root / "wheelhouse"
    manifest_output = manifest_output or plugin_root / "reporter-manifest.json"
    checksums_output = checksums_output or plugin_root / "checksums.json"
    checksums: dict[str, str] = {}
    entries: list[dict[str, object]] = []
    discovered_reporter_versions: set[str] = set()

    for platform, abi in SUPPORTED_WHEELHOUSES:
        directory = wheelhouse_root / platform / abi
        files = wheel_files(directory)
        file_entries = []
        for path in files:
            digest = sha256(path)
            checksums[f"wheelhouse/{platform}/{abi}/{path.name}"] = digest
            file_entries.append({"name": path.name, "sha256": digest})

        reporter_wheels = [
            (path, version)
            for path in files
            for name, version in (wheel_metadata(path),)
            if name.lower().replace("-", "_") == "shopops_reporter"
        ]
        if len(reporter_wheels) != 1:
            raise ValueError(f"Exactly one Reporter wheel is required in {directory}")
        platform_reporter_version = reporter_wheels[0][1]
        discovered_reporter_versions.add(platform_reporter_version)
        entries.append(
            {
                "reporter_version": platform_reporter_version,
                "platform": platform,
                "python": abi.removeprefix("cp"),
                "files": file_entries,
            }
        )

    if reporter_version not in discovered_reporter_versions:
        raise ValueError(f"Reporter {reporter_version} is missing from the staged wheelhouse")

    manifest_output.write_text(
        json.dumps({"wheelhouses": entries}, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    checksums_output.write_text(
        json.dumps(dict(sorted(checksums.items())), indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--action", choices=("write", "locked-requirements", "validate", "promote"), default="write"
    )
    parser.add_argument("--plugin-root", type=Path, required=True)
    parser.add_argument("--reporter-version", required=True)
    parser.add_argument("--platform", default="macos-arm64")
    parser.add_argument("--abi")
    parser.add_argument("--candidate-directory", type=Path)
    parser.add_argument("--wheelhouse-root", type=Path)
    parser.add_argument("--manifest-output", type=Path)
    parser.add_argument("--checksums-output", type=Path)
    parser.add_argument("--staged-platform-root", type=Path)
    parser.add_argument("--staged-manifest", type=Path)
    parser.add_argument("--staged-checksums", type=Path)
    parser.add_argument("--backup-root", type=Path)
    args = parser.parse_args()

    try:
        if args.action == "write":
            write_manifests(
                args.plugin_root,
                args.reporter_version,
                args.wheelhouse_root,
                args.manifest_output,
                args.checksums_output,
            )
        elif args.action == "promote":
            if not all(
                (
                    args.staged_platform_root,
                    args.staged_manifest,
                    args.staged_checksums,
                    args.backup_root,
                )
            ):
                parser.error("promotion requires staged paths and --backup-root")
            promote_release(
                args.plugin_root,
                args.staged_platform_root,
                args.staged_manifest,
                args.staged_checksums,
                args.backup_root,
            )
        else:
            if not args.abi:
                parser.error("--abi is required for lock operations")
            if args.action == "locked-requirements":
                print("\n".join(locked_requirements(args.plugin_root, args.platform, args.abi, args.reporter_version)))
            else:
                if not args.candidate_directory:
                    parser.error("--candidate-directory is required for validation")
                validate_locked_wheelhouse(
                    args.plugin_root,
                    args.platform,
                    args.abi,
                    args.reporter_version,
                    args.candidate_directory,
                )
    except LockUnavailable as error:
        print(error, file=sys.stderr)
        return 2
    except (LockValidationError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
