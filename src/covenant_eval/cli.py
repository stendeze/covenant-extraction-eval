"""Command line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .edgar import MissingUserAgent
from .search import run_census


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="covenant-eval")
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="run the corpus census over EDGAR")
    search.add_argument("--out", type=Path, default=Path("data/search"))

    args = parser.parse_args(argv)

    try:
        if args.command == "search":
            funnel = run_census(args.out)
            print(json.dumps(funnel, indent=2))
    except MissingUserAgent as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0
