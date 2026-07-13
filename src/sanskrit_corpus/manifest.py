from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    name: str
    url: str
    source_type: str
    access_method: str
    license_label: str
    release_status: str
    notes: str


@dataclass(frozen=True)
class PullRunRecord:
    source_id: str
    status: str
    pulled_at: str
    local_path: str
    file_count: int
    byte_count: int
    checksum_sha256: str
    error: str | None = None
    sample: bool = True
    source_revision: str | None = None
    etag: str | None = None
    last_modified: str | None = None


@dataclass(frozen=True)
class ProcessRunRecord:
    run_id: str
    source_id: str
    status: str
    started_at: str
    completed_at: str
    input_checksum_sha256: str
    output_path: str
    record_count: int
    byte_count: int
    checksum_sha256: str
    processor_version: str
    error: str | None = None


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def ensure_manifest_dir(root: Path) -> Path:
    manifest_dir = root / "data" / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    return manifest_dir


def append_jsonl(path: Path, rows: Iterable[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            payload = asdict(cast(Any, row)) if is_dataclass(row) and not isinstance(row, type) else row
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def write_source_registry(root: Path, sources: Iterable[SourceRecord]) -> Path:
    manifest_dir = ensure_manifest_dir(root)
    path = manifest_dir / "source_registry.jsonl"
    path.write_text("", encoding="utf-8")
    append_jsonl(path, sources)
    return path


def directory_stats(path: Path) -> tuple[int, int, str]:
    if not path.exists():
        return 0, 0, ""

    files = sorted(p for p in path.rglob("*") if p.is_file())
    digest = hashlib.sha256()
    total_bytes = 0

    for file_path in files:
        if file_path.name == "_pull_complete.json":
            continue
        relative = file_path.relative_to(path).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        with file_path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
                total_bytes += len(chunk)

    counted_files = sum(file_path.name != "_pull_complete.json" for file_path in files)
    return counted_files, total_bytes, digest.hexdigest()


def file_stats(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    byte_count = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
            byte_count += len(chunk)
    return byte_count, digest.hexdigest()
