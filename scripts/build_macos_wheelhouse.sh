#!/usr/bin/env bash
set -euo pipefail

: "${SHOPOPS_REPO:?Set SHOPOPS_REPO to the ShopOps source checkout.}"

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
REPORTER_DIR="$SHOPOPS_REPO/reporter"
PLUGIN_ROOT="$ROOT_DIR/plugins/shopops-onboarding"
PYTHON_BIN=${PYTHON_BIN:-python3.12}

if [[ ! -f "$REPORTER_DIR/pyproject.toml" ]]; then
  echo "Reporter project not found at $REPORTER_DIR" >&2
  exit 1
fi

if ! "$PYTHON_BIN" -c 'import sys; assert sys.version_info >= (3, 11)' >/dev/null; then
  echo "PYTHON_BIN must be CPython 3.11 or later" >&2
  exit 1
fi

build_dir=$(mktemp -d "${TMPDIR:-/tmp}/shopops-wheelhouse.XXXXXX")
trap 'rm -rf "$build_dir"' EXIT

"$PYTHON_BIN" -m pip wheel --no-deps --wheel-dir "$build_dir" "$REPORTER_DIR"
reporter_wheel=$(find "$build_dir" -maxdepth 1 -type f -name 'shopops_reporter-*.whl' -print -quit)
if [[ -z "$reporter_wheel" ]]; then
  echo "Reporter wheel build did not produce shopops_reporter-*.whl" >&2
  exit 1
fi

reporter_version=$("$PYTHON_BIN" -c 'import sys, tomllib; print(tomllib.load(open(sys.argv[1], "rb"))["project"]["version"])' "$REPORTER_DIR/pyproject.toml")

for abi in cp311 cp312; do
  target="$PLUGIN_ROOT/wheelhouse/macos-arm64/$abi"
  lock_file="$build_dir/$abi-requirements.txt"
  locked=false
  if "$PYTHON_BIN" - "$PLUGIN_ROOT/reporter-manifest.json" "$target" "$reporter_version" "$abi" >"$lock_file" <<'PY'
import json
import sys
from email.parser import BytesParser
from pathlib import Path
from zipfile import ZipFile

manifest_path = Path(sys.argv[1])
wheelhouse = Path(sys.argv[2])
reporter_version = sys.argv[3]
abi = sys.argv[4]

try:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = [
        entry
        for entry in manifest["wheelhouses"]
        if entry["platform"] == "macos-arm64"
        and entry["python"] == abi.removeprefix("cp")
        and entry["reporter_version"] == reporter_version
    ]
    if len(entries) != 1:
        raise ValueError("no matching committed wheelhouse lock")

    expected_files = [item["name"] for item in entries[0]["files"]]
    actual_files = sorted(path.name for path in wheelhouse.glob("*.whl"))
    if expected_files != actual_files:
        raise ValueError("committed wheelhouse does not match its manifest")

    requirements = []
    for filename in actual_files:
        with ZipFile(wheelhouse / filename) as wheel:
            metadata_name = next(
                name for name in wheel.namelist() if name.endswith(".dist-info/METADATA")
            )
            metadata = BytesParser().parsebytes(wheel.read(metadata_name))
        name = metadata["Name"]
        version = metadata["Version"]
        if not name or not version:
            raise ValueError(f"wheel metadata is incomplete: {filename}")
        if name.lower().replace("-", "_") != "shopops_reporter":
            requirements.append(f"{name}=={version}")

    print("\n".join(sorted(requirements)))
except (FileNotFoundError, KeyError, StopIteration, ValueError, json.JSONDecodeError):
    raise SystemExit(1)
PY
  then
    locked=true
  fi
  mkdir -p "$target"
  find "$target" -mindepth 1 -maxdepth 1 -type f -delete
  cp "$reporter_wheel" "$target/"

  requirements=("$reporter_wheel")
  # pip's cross-target resolver does not evaluate these markers for 3.11.
  if [[ "$abi" == "cp311" ]]; then
    requirements+=("importlib-metadata>=4.11.4" "backports.tarfile")
  fi

  if [[ "$locked" == true ]]; then
    "$PYTHON_BIN" -m pip download \
      --no-deps \
      --only-binary=:all: \
      --platform macosx_11_0_arm64 \
      --implementation cp \
      --python-version "${abi:2:1}.${abi:3}" \
      --abi "$abi" \
      --dest "$target" \
      --requirement "$lock_file"
  else
    "$PYTHON_BIN" -m pip download \
      --only-binary=:all: \
      --platform macosx_11_0_arm64 \
      --implementation cp \
      --python-version "${abi:2:1}.${abi:3}" \
      --abi "$abi" \
      --dest "$target" \
      "${requirements[@]}"
  fi

  if find "$target" -maxdepth 1 -type f ! -name '*.whl' -print -quit | grep -q .; then
    echo "Source distributions and non-wheel artifacts are not allowed in $target" >&2
    exit 1
  fi
done

"$PYTHON_BIN" "$ROOT_DIR/scripts/write_checksums.py" \
  --plugin-root "$PLUGIN_ROOT" \
  --reporter-version "$reporter_version"
