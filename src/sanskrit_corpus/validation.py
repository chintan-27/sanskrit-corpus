from __future__ import annotations

import json
import sqlite3
import tempfile
from collections import Counter
from importlib.resources import files
from pathlib import Path
from typing import Any
from uuid import uuid4

import fastjsonschema  # type: ignore[import-untyped]

from .exporting import PROFILE_STATUSES
from .licensing import apply_license
from .manifest import utc_now


def validate_processed(
    root: Path,
    source_id: str = "all",
    profile: str | None = None,
    max_errors: int = 100,
) -> dict[str, Any]:
    if max_errors < 0:
        raise ValueError("max_errors must be non-negative")
    if profile is not None and profile not in PROFILE_STATUSES:
        raise ValueError(f"unknown export profile: {profile}")

    schema = json.loads(files("sanskrit_corpus").joinpath("record.schema.json").read_text(encoding="utf-8"))
    validate_row = fastjsonschema.compile(schema)
    processed = root / "data" / "processed"
    paths = sorted(processed.glob("*.jsonl")) if source_id == "all" else [processed / f"{source_id}.jsonl"]
    counts: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []

    def issue(level: str, code: str, path: Path, line_number: int, message: str) -> None:
        counts[level] += 1
        counts[f"{level}:{code}"] += 1
        if len(examples) < max_errors:
            examples.append({"level": level, "code": code, "path": str(path), "line_number": line_number, "message": message})
        elif level == "error":
            for index in range(len(examples) - 1, -1, -1):
                if examples[index]["level"] == "warning":
                    examples[index] = {
                        "level": level,
                        "code": code,
                        "path": str(path),
                        "line_number": line_number,
                        "message": message,
                    }
                    break

    allowed = PROFILE_STATUSES[profile] if profile else None
    with tempfile.TemporaryDirectory(prefix="sanskrit-corpus-validation-") as temporary:
        connection = sqlite3.connect(str(Path(temporary) / "record_ids.sqlite3"))
        connection.execute("CREATE TABLE record_ids (record_id TEXT PRIMARY KEY)")
        for path in paths:
            if not path.exists():
                issue("error", "missing_input", path, 0, "processed JSONL does not exist")
                continue
            counts["files"] += 1
            with path.open(encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip():
                        issue("warning", "blank_line", path, line_number, "blank JSONL line")
                        continue
                    counts["scanned_records"] += 1
                    try:
                        embedded = json.loads(line)
                    except json.JSONDecodeError as exc:
                        issue("error", "invalid_json", path, line_number, str(exc))
                        continue
                    if not isinstance(embedded, dict):
                        issue("error", "invalid_type", path, line_number, "record must be a JSON object")
                        continue
                    row = apply_license(root, embedded)
                    if allowed is not None and row.get("release_status") not in allowed:
                        continue
                    counts["validated_records"] += 1
                    try:
                        validate_row(row)
                    except fastjsonschema.JsonSchemaException as exc:
                        issue("error", "schema", path, line_number, exc.message)
                        continue
                    record_id = str(row["record_id"])
                    try:
                        connection.execute("INSERT INTO record_ids VALUES (?)", (record_id,))
                    except sqlite3.IntegrityError:
                        issue("error", "duplicate_record_id", path, line_number, record_id)
                    if row.get("record_type") == "ner_sentence":
                        tokens = row.get("tokens") or []
                        tags = row.get("ner_tags") or []
                        if len(tokens) != len(tags):
                            issue("error", "ner_length_mismatch", path, line_number, f"{len(tokens)} tokens != {len(tags)} tags")
                    if str(row.get("text_lang", "")).startswith("sa-Deva") and _devanagari_ratio(str(row.get("text", ""))) < 0.45:
                        issue("warning", "low_devanagari_ratio", path, line_number, "less than 45% of letters are Devanagari")
                    if "processing_run_id" not in row:
                        issue("warning", "legacy_provenance", path, line_number, "record predates processing run provenance")
        connection.commit()
        connection.close()

    return {
        "status": "failed" if counts["error"] else "ok",
        "validated_at": utc_now(),
        "source_id": source_id,
        "profile": profile,
        "counts": dict(sorted(counts.items())),
        "examples": examples,
    }


def write_validation_report(root: Path, report: dict[str, Any], file_name: str = "validation_summary.json") -> Path:
    output = root / "data" / "reports" / file_name
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{uuid4().hex}.tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(output)
    return output


def _devanagari_ratio(text: str) -> float:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return 0.0
    return sum("\u0900" <= char <= "\u097f" for char in letters) / len(letters)
