"""Command line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .edgar import MissingUserAgent
from .screen import run_screen
from .search import run_census
from .validate import run_validate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="covenant-eval")
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="run the corpus census over EDGAR")
    search.add_argument("--out", type=Path, default=Path("data/search"))

    screen = sub.add_parser("screen", help="download and screen candidate documents")
    screen.add_argument("--candidates", type=Path, default=Path("data/search/candidates.jsonl"))
    screen.add_argument("--out", type=Path, default=Path("data/screen"))
    screen.add_argument("--raw", type=Path, default=Path("data/raw"))
    screen.add_argument("--limit", type=int, default=400)
    screen.add_argument("--seed", type=int, default=20260904)

    validate = sub.add_parser(
        "validate", help="check label files against the current schema, reporting only"
    )
    validate.add_argument("paths", type=Path, nargs="*", default=[Path("data/labels")])
    validate.add_argument("--raw", type=Path, default=Path("data/raw"))

    args = parser.parse_args(argv)

    try:
        if args.command == "search":
            result = run_census(args.out)
        elif args.command == "screen":
            result = run_screen(
                args.candidates, args.out, limit=args.limit,
                seed=args.seed, raw_dir=args.raw,
            )
        elif args.command == "validate":
            paths = args.paths or [Path("data/labels")]
            result = run_validate(paths, args.raw)
            print(
                f"\n{result['clean']} clean, {result['with_deviations']} with deviations, "
                f"{result['total_deviations']} deviations ({result['total_errors']} errors)"
            )
            # Non-zero on errors so the audit can gate a commit. Warnings do
            # not fail: several of them are judgment calls the labeler owns.
            return 1 if result["total_errors"] else 0
        print(json.dumps(result, indent=2))
    except MissingUserAgent as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0
