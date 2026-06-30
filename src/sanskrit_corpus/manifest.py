from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


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
            payload = asdict(row) if hasattr(row, "__dataclass_fields__") else row
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
        relative = file_path.relative_to(path).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        data = file_path.read_bytes()
        digest.update(data)
        total_bytes += len(data)

    return len(files), total_bytes, digest.hexdigest()
