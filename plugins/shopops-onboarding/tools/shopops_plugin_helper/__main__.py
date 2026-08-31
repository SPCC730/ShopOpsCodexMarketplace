"""JSON command-line interface for ShopOps plugin utilities."""

from __future__ import annotations

import argparse
import contextlib
from dataclasses import asdict
import json
from pathlib import Path
import sys
from typing import Sequence

from .environment import EnvironmentProbe, probe_environment
from .installer import (
    InstallError,
    default_reporter_home,
    install_preview,
    install_reporter,
)


_PLUGIN_ROOT = Path(__file__).resolve().parents[2]


def main(argv: Sequence[str] | None = None) -> int:
    """Run a supported helper command."""
    parser = argparse.ArgumentParser(prog="shopops-plugin-helper")
    subcommands = parser.add_subparsers(dest="command", required=True)
    probe_parser = subcommands.add_parser("probe")
    probe_parser.add_argument("--json", action="store_true", required=True)
    preview_parser = subcommands.add_parser("install-preview")
    preview_parser.add_argument("--json", action="store_true", required=True)
    install_parser = subcommands.add_parser("install")
    install_parser.add_argument("--confirm-version", required=True)
    install_parser.add_argument("--json", action="store_true", required=True)
    args = parser.parse_args(argv)

    try:
        with contextlib.redirect_stdout(sys.stderr):
            exit_code, payload = _dispatch(args)
    except InstallError as error:
        exit_code, payload = 2, {"schema_version": 1, "error": str(error) or "install_failed"}
    except OSError:
        exit_code, payload = 2, {"schema_version": 1, "error": "filesystem_error"}
    except Exception:
        exit_code, payload = 2, {"schema_version": 1, "error": "internal_error"}
    print(json.dumps(payload))
    return exit_code


def _dispatch(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    """Return one versioned result without writing unstructured standard output."""

    if args.command == "probe":
        probe = probe_environment()
        return (0 if probe.supported else 1), {
            "schema_version": 1,
            "environment": asdict(probe),
        }

    if args.command in {"install-preview", "install"}:
        probe = probe_environment()
        reporter_home = default_reporter_home()
        preview = install_preview(_PLUGIN_ROOT, reporter_home, probe)

        if args.command == "install-preview":
            return 0, {"schema_version": 1, "install": asdict(preview)}

        if args.confirm_version != preview.version:
            return 2, {
                "schema_version": 1,
                "error": "confirmation_version_mismatch",
                "version": preview.version,
            }
        installed = install_reporter(_PLUGIN_ROOT, reporter_home, probe)
        return 0, {"schema_version": 1, "install": asdict(installed)}

    return 2, {"schema_version": 1, "error": "unknown_command"}


if __name__ == "__main__":
    raise SystemExit(main())
