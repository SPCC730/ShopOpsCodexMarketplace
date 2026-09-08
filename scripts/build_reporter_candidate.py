#!/usr/bin/env python3
"""Stage a release candidate using the existing verified dependency wheels."""

import argparse
import json
from pathlib import Path
import shutil

from write_checksums import SUPPORTED_WHEELHOUSES, sha256, wheel_metadata, write_manifests


def build_candidate(plugin_root: Path, reporter_wheel: Path, destination: Path) -> Path:
    name, version = wheel_metadata(reporter_wheel)
    if name.lower().replace('-', '_') != 'shopops_reporter':
        raise ValueError('expected_reporter_wheel')
    checksums = json.loads((plugin_root / 'checksums.json').read_text())
    for relative, expected in checksums.items():
        if sha256(plugin_root / relative) != expected:
            raise ValueError(f'existing_wheel_checksum_mismatch:{relative}')
    if destination.exists():
        raise ValueError('candidate_exists_choose_new_destination')
    candidate = destination / 'plugins' / plugin_root.name
    shutil.copytree(plugin_root, candidate, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    for platform, abi in SUPPORTED_WHEELHOUSES:
        directory = candidate / 'wheelhouse' / platform / abi
        old = list(directory.glob('shopops_reporter-*.whl'))
        if len(old) != 1:
            raise ValueError('expected_one_reporter_wheel')
        old[0].unlink()
        shutil.copy2(reporter_wheel, directory / reporter_wheel.name)
    write_manifests(candidate, version)
    return candidate


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--plugin-root', type=Path, required=True)
    parser.add_argument('--reporter-wheel', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    print(build_candidate(args.plugin_root, args.reporter_wheel, args.destination))
