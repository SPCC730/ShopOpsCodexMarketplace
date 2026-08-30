"""JSON command-line interface for ShopOps plugin utilities."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
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

    if args.command == "probe":
        probe = probe_environment()
        print(json.dumps({"schema_version": 1, "environment": asdict(probe)}))
        return 0 if probe.supported else 1

    if args.command in {"install-preview", "install"}:
        probe = probe_environment()
        reporter_home = default_reporter_home()
        try:
            preview = install_preview(_PLUGIN_ROOT, reporter_home, probe)
        except InstallError as error:
            print(json.dumps({"schema_version": 1, "error": str(error)}))
            return 2

        if args.command == "install-preview":
            print(json.dumps({"schema_version": 1, "install": asdict(preview)}))
            return 0

        if args.confirm_version != preview.version:
            print(
                json.dumps(
                    {
                        "schema_version": 1,
                        "error": "confirmation_version_mismatch",
                        "version": preview.version,
                    }
                )
            )
            return 2
        try:
            installed = install_reporter(_PLUGIN_ROOT, reporter_home, probe)
        except InstallError as error:
            print(json.dumps({"schema_version": 1, "error": str(error)}))
            return 2
        print(json.dumps({"schema_version": 1, "install": asdict(installed)}))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
