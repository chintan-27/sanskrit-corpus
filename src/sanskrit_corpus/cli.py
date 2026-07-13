from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .exporting import export_profile, write_audit
from .internet_archive import DEFAULT_IA_QUERY, pull_internet_archive
from .manifest import append_jsonl, ensure_manifest_dir, write_source_registry
from .processing import process_sources
from .reporting import write_report
from .sources import PullContext, build_sources
from .validation import validate_processed, write_validation_report


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def non_negative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sanskrit-corpus")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pull = subparsers.add_parser("pull", help="Pull available corpus sources into data/raw.")
    pull.add_argument("--source", default="all", help="Source id to pull, or 'all'.")
    mode = pull.add_mutually_exclusive_group()
    mode.add_argument("--sample", action="store_true", default=True, help="Pull a small source sample where supported.")
    mode.add_argument("--full", action="store_true", help="Pull all files exposed by the source adapter.")
    pull.add_argument("--dry-run", action="store_true", help="List planned sources without downloading.")
    pull.add_argument("--force", action="store_true", help="Replace existing local source directories.")
    pull.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")

    process = subparsers.add_parser("process", help="Normalize pulled raw sources into data/processed JSONL.")
    process.add_argument("--source", default="all", help="Source id to process, or 'all'.")
    process.add_argument("--limit", type=non_negative_int, help="Maximum records to emit per source.")
    process.add_argument("--force", action="store_true", help="Replace existing processed JSONL files.")
    process.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")

    report = subparsers.add_parser("report", help="Write a local corpus acquisition summary.")
    report.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")

    audit = subparsers.add_parser("audit", help="Write release-status and license audit summary.")
    audit.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")

    validate = subparsers.add_parser("validate", help="Validate processed JSONL records and corpus integrity.")
    validate.add_argument("--source", default="all", help="Source id to validate, or 'all'.")
    validate.add_argument("--max-errors", type=non_negative_int, default=100, help="Maximum issue examples to retain.")
    validate.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")

    export = subparsers.add_parser("export", help="Export a filtered JSONL release profile.")
    export.add_argument(
        "--profile",
        default="releasable",
        help="Export profile: releasable, clean_releasable, benchmark, synthetic, needs_audit, all.",
    )
    export.add_argument("--force", action="store_true", help="Replace an existing release file.")
    export.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")

    ia_pull = subparsers.add_parser("ia-pull", help="Pull Internet Archive files with a byte quota.")
    ia_pull.add_argument("--query", default=DEFAULT_IA_QUERY, help="Internet Archive advanced search query.")
    ia_pull.add_argument("--limit", type=non_negative_int, default=25, help="Maximum archive items to inspect.")
    ia_pull.add_argument("--max-gb", type=non_negative_float, default=1.0, help="Maximum downloaded bytes in GiB.")
    ia_pull.add_argument("--file-kind", default="ocr_text", choices=["ocr_text", "pdf", "all"], help="Derivative files to download.")
    ia_pull.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")

    return parser


def run_pull(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    sources = build_sources()
    write_source_registry(root, [source.record for source in sources.values()])

    if args.source == "all":
        selected = list(sources.values())
    else:
        if args.source not in sources:
            known = ", ".join(sorted(sources))
            print(f"unknown source '{args.source}'. Known sources: {known}", file=sys.stderr)
            return 2
        selected = [sources[args.source]]

    context = PullContext(root=root, sample=not args.full, dry_run=args.dry_run, force=args.force)
    run_rows = []
    for source in selected:
        row = source.pull(context)
        run_rows.append(row)
        print(f"{row.status:8} {source.record.source_id} -> {row.local_path}")
        if row.error:
            print(f"         {row.error}")

    manifest_dir = ensure_manifest_dir(root)
    append_jsonl(manifest_dir / "pull_runs.jsonl", run_rows)
    return 1 if any(row.status == "failed" for row in run_rows if args.source != "all") else 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "pull":
        return run_pull(args)
    if args.command == "process":
        return run_process(args)
    if args.command == "report":
        return run_report(args)
    if args.command == "audit":
        return run_audit(args)
    if args.command == "validate":
        return run_validate(args)
    if args.command == "export":
        return run_export(args)
    if args.command == "ia-pull":
        return run_ia_pull(args)
    parser.error(f"unsupported command {args.command}")
    return 2


def run_process(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    results = process_sources(root, source_id=args.source, force=args.force, limit=args.limit)
    for result in results:
        print(f"{result.status:8} {result.source_id} -> {result.output_path} ({result.record_count} records)")
        if result.error:
            print(f"         {result.error}")
    return 1 if any(result.status in {"failed", "empty", "missing_input"} for result in results) else 0


def run_report(args: argparse.Namespace) -> int:
    path = write_report(Path(args.root).resolve())
    print(f"ok       report -> {path}")
    return 0


def run_audit(args: argparse.Namespace) -> int:
    path = write_audit(Path(args.root).resolve())
    print(f"ok       audit -> {path}")
    return 0


def run_validate(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    report = validate_processed(root, source_id=args.source, max_errors=args.max_errors)
    path = write_validation_report(root, report)
    errors = report["counts"].get("error", 0)
    warnings = report["counts"].get("warning", 0)
    print(f"{report['status']:8} validate -> {path} ({errors} errors, {warnings} warnings)")
    return 1 if errors else 0


def run_export(args: argparse.Namespace) -> int:
    try:
        path, count = export_profile(Path(args.root).resolve(), profile=args.profile, force=args.force)
    except (FileExistsError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"ok       export:{args.profile} -> {path} ({count} records)")
    return 0


def run_ia_pull(args: argparse.Namespace) -> int:
    result = pull_internet_archive(
        Path(args.root).resolve(),
        query=args.query,
        limit=args.limit,
        max_gb=args.max_gb,
        file_kind=args.file_kind,
    )
    print(
        f"{result.status:8} internet_archive -> {result.file_count} files, "
        f"{result.byte_count} bytes, {result.item_count} items"
    )
    print(f"         manifest: {result.manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
