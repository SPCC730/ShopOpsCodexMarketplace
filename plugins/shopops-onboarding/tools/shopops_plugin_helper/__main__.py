"""JSON command-line interface for ShopOps plugin utilities."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from typing import Sequence

from .environment import EnvironmentProbe, probe_environment


def main(argv: Sequence[str] | None = None) -> int:
    """Run a supported helper command."""
    parser = argparse.ArgumentParser(prog="shopops-plugin-helper")
    subcommands = parser.add_subparsers(dest="command", required=True)
    probe_parser = subcommands.add_parser("probe")
    probe_parser.add_argument("--json", action="store_true", required=True)
    args = parser.parse_args(argv)

    if args.command == "probe":
        probe = probe_environment()
        print(json.dumps({"schema_version": 1, "environment": asdict(probe)}))
        return 0 if probe.supported else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
