#!/usr/bin/env python3
"""Write deterministic wheelhouse manifests from vendored binary wheels."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SUPPORTED_WHEELHOUSES = (("macos-arm64", "cp311"), ("macos-arm64", "cp312"))


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


def write_manifests(plugin_root: Path, reporter_version: str) -> None:
    wheelhouse_root = plugin_root / "wheelhouse"
    checksums: dict[str, str] = {}
    entries: list[dict[str, object]] = []

    for platform, abi in SUPPORTED_WHEELHOUSES:
        directory = wheelhouse_root / platform / abi
        files = wheel_files(directory)
        file_entries = []
        for path in files:
            relative = path.relative_to(plugin_root).as_posix()
            digest = sha256(path)
            checksums[relative] = digest
            file_entries.append({"name": path.name, "sha256": digest})

        if not any(path.name.startswith(f"shopops_reporter-{reporter_version}-") for path in files):
            raise ValueError(f"Reporter {reporter_version} is missing from {directory}")
        entries.append(
            {
                "reporter_version": reporter_version,
                "platform": platform,
                "python": abi.removeprefix("cp"),
                "files": file_entries,
            }
        )

    manifest = {"wheelhouses": entries}
    (plugin_root / "reporter-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (plugin_root / "checksums.json").write_text(
        json.dumps(dict(sorted(checksums.items())), indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin-root", type=Path, required=True)
    parser.add_argument("--reporter-version", required=True)
    args = parser.parse_args()
    write_manifests(args.plugin_root, args.reporter_version)


if __name__ == "__main__":
    main()
