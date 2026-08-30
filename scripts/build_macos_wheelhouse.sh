#!/usr/bin/env bash
set -euo pipefail

: "${SHOPOPS_REPO:?Set SHOPOPS_REPO to the ShopOps source checkout.}"

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
REPORTER_DIR="$SHOPOPS_REPO/reporter"
PLUGIN_ROOT="$ROOT_DIR/plugins/shopops-onboarding"
PYTHON_BIN=${PYTHON_BIN:-python3.12}
WRITER="$ROOT_DIR/scripts/write_checksums.py"

if [[ ! -f "$REPORTER_DIR/pyproject.toml" ]]; then
  echo "Reporter project not found at $REPORTER_DIR" >&2
  exit 1
fi
if ! "$PYTHON_BIN" -c 'import sys; assert sys.version_info >= (3, 11)' >/dev/null; then
  echo "PYTHON_BIN must be CPython 3.11 or later" >&2
  exit 1
fi

mkdir -p "$PLUGIN_ROOT/wheelhouse"
build_dir=$(mktemp -d "$PLUGIN_ROOT/.wheelhouse-release.XXXXXX")
trap 'rm -rf "$build_dir"' EXIT
staged_wheelhouse="$build_dir/wheelhouse"
staged_platform_root="$staged_wheelhouse/macos-arm64"
staged_manifest="$build_dir/reporter-manifest.json"
staged_checksums="$build_dir/checksums.json"

"$PYTHON_BIN" -m pip wheel --no-deps --wheel-dir "$build_dir" "$REPORTER_DIR"
reporter_wheel=$(find "$build_dir" -maxdepth 1 -type f -name 'shopops_reporter-*.whl' -print -quit)
if [[ -z "$reporter_wheel" ]]; then
  echo "Reporter wheel build did not produce shopops_reporter-*.whl" >&2
  exit 1
fi
reporter_version=$("$PYTHON_BIN" -c 'import sys, tomllib; print(tomllib.load(open(sys.argv[1], "rb"))["project"]["version"])' "$REPORTER_DIR/pyproject.toml")

for abi in cp311 cp312; do
  stage="$staged_platform_root/$abi"
  lock_file="$build_dir/$abi-requirements.txt"
  mkdir -p "$stage"
  locked=false

  set +e
  "$PYTHON_BIN" "$WRITER" \
    --action locked-requirements \
    --plugin-root "$PLUGIN_ROOT" \
    --reporter-version "$reporter_version" \
    --platform macos-arm64 \
    --abi "$abi" >"$lock_file"
  lock_status=$?
  set -e
  case "$lock_status" in
    0) locked=true ;;
    2) ;;
    *)
      echo "Committed $abi lock validation failed; live payload was not modified." >&2
      exit "$lock_status"
      ;;
  esac

  cp "$reporter_wheel" "$stage/"
  if [[ "$locked" == true ]]; then
    "$PYTHON_BIN" -m pip download \
      --no-deps \
      --require-hashes \
      --only-binary=:all: \
      --platform macosx_11_0_arm64 \
      --implementation cp \
      --python-version "${abi:2:1}.${abi:3}" \
      --abi "$abi" \
      --dest "$stage" \
      --requirement "$lock_file"
  else
    requirements=("$reporter_wheel")
    # pip's cross-target resolver does not evaluate these markers for 3.11.
    if [[ "$abi" == "cp311" ]]; then
      requirements+=("importlib-metadata>=4.11.4" "backports.tarfile")
    fi
    "$PYTHON_BIN" -m pip download \
      --only-binary=:all: \
      --platform macosx_11_0_arm64 \
      --implementation cp \
      --python-version "${abi:2:1}.${abi:3}" \
      --abi "$abi" \
      --dest "$stage" \
      "${requirements[@]}"
  fi

  if find "$stage" -maxdepth 1 -type f ! -name '*.whl' -print -quit | grep -q .; then
    echo "Source distributions and non-wheel artifacts are not allowed in $stage" >&2
    exit 1
  fi
  if [[ "$locked" == true ]]; then
    "$PYTHON_BIN" "$WRITER" \
      --action validate \
      --plugin-root "$PLUGIN_ROOT" \
      --reporter-version "$reporter_version" \
      --platform macos-arm64 \
      --abi "$abi" \
      --candidate-directory "$stage"
  fi
done

"$PYTHON_BIN" "$WRITER" \
  --plugin-root "$PLUGIN_ROOT" \
  --reporter-version "$reporter_version" \
  --wheelhouse-root "$staged_wheelhouse" \
  --manifest-output "$staged_manifest" \
  --checksums-output "$staged_checksums"

"$PYTHON_BIN" "$WRITER" \
  --action promote \
  --plugin-root "$PLUGIN_ROOT" \
  --reporter-version "$reporter_version" \
  --staged-platform-root "$staged_platform_root" \
  --staged-manifest "$staged_manifest" \
  --staged-checksums "$staged_checksums" \
  --backup-root "$build_dir/backup"
