"""Command line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .edgar import MissingUserAgent
from .extract import RUNS_DIR, CorpusLocked, Settings, score_run
from .extract import run as run_extraction
from .screen import run_screen
from .search import run_census
from .coverage import run_coverage, write_results
from .prompt import run_prompt
from .score import run_agree, run_compare
from .validate import SCHEMA_PATH, SchemaParseError, run_validate


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
    validate.add_argument("--schema", type=Path, default=SCHEMA_PATH)

    coverage = sub.add_parser(
        "coverage", help="what the gold set exercises, with instance counts and naive baselines"
    )
    coverage.add_argument("--labels", type=Path, default=Path("data/labels"))
    coverage.add_argument("--schema", type=Path, default=SCHEMA_PATH)
    coverage.add_argument(
        "--write", type=Path, metavar="RESULTS_MD",
        help="regenerate the baseline table and coverage snapshot in place",
    )

    compare = sub.add_parser(
        "compare", help="align two label-shaped records of one agreement and compare every scored field"
    )
    compare.add_argument("reference", type=Path)
    compare.add_argument("candidate", type=Path)
    compare.add_argument(
        "--symmetric", action="store_true",
        help="either side may exclude a field, and null kinds are compared (the relabel's comparison)",
    )
    compare.add_argument("--values", action="store_true", help="print both values beside each field")
    compare.add_argument("--schema", type=Path, default=SCHEMA_PATH)

    agree = sub.add_parser(
        "agree", help="the blind relabel's per-field agreement: rates and counts, never values"
    )
    agree.add_argument("--original", type=Path, default=Path("data/labels"))
    agree.add_argument("--relabel", type=Path, default=Path("data/relabel"))
    agree.add_argument(
        "--exposure", type=Path,
        help="fields the repository already answers, as JSON [{document_file, level, record, field, tier}]",
    )
    agree.add_argument("--schema", type=Path, default=SCHEMA_PATH)

    prompt = sub.add_parser(
        "prompt", help="generate the extraction prompt and output schema from schema.md (check, or --write)"
    )
    prompt.add_argument("--write", action="store_true", help="replace the committed prompt and schema")
    prompt.add_argument("--schema", type=Path, default=SCHEMA_PATH)

    extract = sub.add_parser(
        "extract", help="prepare an extraction run over labeled documents; --submit sends it to the Batch API"
    )
    extract.add_argument("labels", type=Path, nargs="+", help="label-shaped files naming the documents")
    extract.add_argument("--run-id", required=True)
    extract.add_argument("--submit", action="store_true", help="send the batch (costs money; needs credentials)")
    extract.add_argument("--model", default=Settings.model)
    extract.add_argument("--effort", default=Settings.effort)
    extract.add_argument("--max-tokens", type=int, default=Settings.max_tokens)
    extract.add_argument("--poll", type=float, default=60, help="seconds between batch status checks")

    score_run_p = sub.add_parser("score-run", help="compare a run's predictions with label files: counts, no values")
    score_run_p.add_argument("run_id")
    score_run_p.add_argument("--labels", type=Path, default=Path("data/dev"))

    args = parser.parse_args(argv)

    try:
        if args.command == "extract":
            settings = Settings(model=args.model, effort=args.effort, max_tokens=args.max_tokens)
            print(run_extraction(args.run_id, args.labels, submit_batch=args.submit, settings=settings,
                                 poll_seconds=args.poll))
            return 0
        if args.command == "score-run":
            print(score_run(RUNS_DIR / args.run_id, args.labels))
            return 0
        if args.command == "prompt":
            report = run_prompt(args.write, args.schema)
            print(report)
            return 0 if args.write or "DIFFERS" not in report else 1
        if args.command == "compare":
            print(run_compare(args.reference, args.candidate, args.schema,
                              symmetric=args.symmetric, values=args.values))
            return 0
        if args.command == "agree":
            print(run_agree(args.original, args.relabel, args.exposure, args.schema))
            return 0
        if args.command == "search":
            result = run_census(args.out)
        elif args.command == "screen":
            result = run_screen(
                args.candidates, args.out, limit=args.limit,
                seed=args.seed, raw_dir=args.raw,
            )
        elif args.command == "coverage":
            if args.write:
                write_results(args.write, args.labels, args.schema)
                print(f"regenerated {args.write}")
            else:
                print(run_coverage(args.labels, args.schema))
            return 0
        elif args.command == "validate":
            paths = args.paths or [Path("data/labels")]
            result = run_validate(paths, args.raw, args.schema)
            print(
                f"\n{result['clean']} clean, {result['with_deviations']} with deviations, "
                f"{result['total_deviations']} deviations ({result['total_errors']} errors)"
            )
            # Non-zero on errors so the audit can gate a commit. Warnings do
            # not fail: several of them are judgment calls the labeler owns.
            return 1 if result["total_errors"] else 0
        print(json.dumps(result, indent=2))
    except (MissingUserAgent, SchemaParseError, CorpusLocked, FileExistsError) as exc:
        # Exit 2 is "cannot run", distinct from exit 1, "ran and found
        # deviations". A schema.md that will not parse must not degrade into a
        # clean-looking report computed from a partial value set.
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0
