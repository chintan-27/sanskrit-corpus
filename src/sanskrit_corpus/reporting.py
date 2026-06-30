from __future__ import annotations

import json
from pathlib import Path


def build_report(root: Path) -> dict[str, object]:
    raw_dir = root / "data" / "raw"
    processed_dir = root / "data" / "processed"
    return {
        "raw_sources": _directory_sizes(raw_dir),
        "processed_outputs": _jsonl_outputs(processed_dir),
    }


def write_report(root: Path) -> Path:
    report = build_report(root)
    path = root / "data" / "reports" / "corpus_summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _directory_sizes(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows = []
    for child in sorted(p for p in path.iterdir() if p.is_dir()):
        files = [p for p in child.rglob("*") if p.is_file()]
        rows.append(
            {
                "source_id": child.name,
                "file_count": len(files),
                "byte_count": sum(p.stat().st_size for p in files),
            }
        )
    return rows


def _jsonl_outputs(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows = []
    for file_path in sorted(path.glob("*.jsonl")):
        line_count = 0
        with file_path.open(encoding="utf-8") as handle:
            for line_count, _ in enumerate(handle, start=1):
                pass
        rows.append(
            {
                "source_id": file_path.stem,
                "record_count": line_count,
                "byte_count": file_path.stat().st_size,
            }
        )
    return rows
