from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .manifest import append_jsonl, ensure_manifest_dir, write_source_registry
from .sources import PullContext, build_sources


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
    parser.error(f"unsupported command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
