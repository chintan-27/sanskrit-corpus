from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unicodedata
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq

from .manifest import utc_now


@dataclass(frozen=True)
class QualitySource:
    source_id: str
    partition: str
    provenance_class: str


SANGRAHA_QUALITY_SOURCES = (
    QualitySource("sangraha_verified_sanskrit", "verified/san", "human_source_verified"),
    QualitySource("sangraha_unverified_sanskrit", "unverified/san", "human_source_unverified"),
    QualitySource("sangraha_synthetic_sanskrit_deva", "synthetic/san_Deva", "synthetic_translation"),
)

QUALITY_SCHEMA = pa.schema(
    [
        ("record_id", pa.string()),
        ("source_id", pa.string()),
        ("source_path", pa.string()),
        ("source_document_id", pa.string()),
        ("corpus_partition", pa.string()),
        ("provenance_class", pa.string()),
        ("content_sha256", pa.string()),
        ("duplicate", pa.bool_()),
        ("duplicate_of", pa.string()),
        ("character_count", pa.int64()),
        ("word_count", pa.int64()),
        ("devanagari_ratio", pa.float32()),
        ("latin_ratio", pa.float32()),
        ("replacement_count", pa.int32()),
        ("control_count", pa.int32()),
        ("dominant_token_ratio", pa.float32()),
        ("quality_score", pa.float32()),
        ("curriculum_tier", pa.string()),
        ("quality_flags", pa.list_(pa.string())),
    ]
)


def profile_sangraha_quality(
    root: Path,
    source_id: str = "all",
    force: bool = False,
    limit: int | None = None,
    workers: int = 1,
) -> Path:
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative")
    if workers < 1:
        raise ValueError("workers must be positive")
    sources = _select_sources(source_id)
    quality_dir = root / "data" / "quality"
    quality_dir.mkdir(parents=True, exist_ok=True)
    outputs = {source.source_id: quality_dir / f"{source.source_id}.parquet" for source in sources}
    existing = [path for path in outputs.values() if path.exists()]
    if existing and not force:
        raise FileExistsError(f"{existing[0]} already exists; pass --force to replace it")

    summary_counts: dict[str, Counter[str]] = {}
    temporary_outputs = {source_id: path.with_name(f".{path.name}.{uuid4().hex}.tmp") for source_id, path in outputs.items()}
    writers: dict[str, pq.ParquetWriter] = {}
    dedup_path: Path | None = None
    executor = ProcessPoolExecutor(max_workers=workers) if workers > 1 else None
    try:
        with tempfile.NamedTemporaryFile(prefix="sanskrit-quality-dedup-", suffix=".sqlite3", dir=quality_dir, delete=False) as handle:
            dedup_path = Path(handle.name)
        connection = sqlite3.connect(dedup_path)
        connection.execute("PRAGMA synchronous=OFF")
        connection.execute("PRAGMA journal_mode=OFF")
        connection.execute("CREATE TABLE content (content_sha256 TEXT PRIMARY KEY, record_id TEXT NOT NULL)")

        for source in sources:
            writer = pq.ParquetWriter(temporary_outputs[source.source_id], QUALITY_SCHEMA, compression="zstd")
            writers[source.source_id] = writer
            counts: Counter[str] = Counter()
            summary_counts[source.source_id] = counts
            emitted = 0
            buffered: list[dict[str, Any]] = []
            raw_dir = root / "data" / "raw" / source.source_id / source.partition
            for parquet_path in sorted(raw_dir.glob("*.parquet")):
                relative_path = parquet_path.relative_to(root / "data" / "raw" / source.source_id).as_posix()
                parquet = pq.ParquetFile(parquet_path)
                available = set(parquet.schema_arrow.names)
                if "text" not in available:
                    raise ValueError(f"Sangraha shard lacks required text column: {relative_path}")
                columns = [column for column in ("doc_id", "text") if column in available]
                row_number = 0
                for batch in parquet.iter_batches(batch_size=512, columns=columns):
                    payloads = batch.to_pylist()
                    jobs = [(str(payload.get("text") or ""), source.provenance_class) for payload in payloads]
                    if executor is None:
                        analyses = [_analyze_and_hash(job) for job in jobs]
                    else:
                        analyses = list(executor.map(_analyze_and_hash, jobs, chunksize=32))
                    for payload, (text, digest, quality) in zip(payloads, analyses, strict=True):
                        row_number += 1
                        if not text:
                            counts["empty"] += 1
                            continue
                        document_id = str(payload.get("doc_id") or row_number)
                        record_id = f"{source.source_id}:{relative_path}:{document_id}"
                        cursor = connection.execute("INSERT OR IGNORE INTO content VALUES (?, ?)", (digest, record_id))
                        duplicate = cursor.rowcount == 0
                        duplicate_of = None
                        if duplicate:
                            existing_row = connection.execute(
                                "SELECT record_id FROM content WHERE content_sha256 = ?",
                                (digest,),
                            ).fetchone()
                            duplicate_of = str(existing_row[0])
                            quality["curriculum_tier"] = "exact_duplicate"
                            quality["quality_flags"] = [*quality["quality_flags"], "exact_duplicate"]
                            counts["duplicates"] += 1
                        tier = str(quality["curriculum_tier"])
                        counts[f"tier:{tier}"] += 1
                        for flag in quality["quality_flags"]:
                            counts[f"flag:{flag}"] += 1
                        buffered.append(
                            {
                                "record_id": record_id,
                                "source_id": source.source_id,
                                "source_path": relative_path,
                                "source_document_id": document_id,
                                "corpus_partition": source.partition,
                                "provenance_class": source.provenance_class,
                                "content_sha256": digest,
                                "duplicate": duplicate,
                                "duplicate_of": duplicate_of,
                                **quality,
                            }
                        )
                        emitted += 1
                        counts["profiled"] += 1
                        if len(buffered) >= 2048:
                            writer.write_table(pa.Table.from_pylist(buffered, schema=QUALITY_SCHEMA))
                            buffered = []
                            connection.commit()
                        if limit is not None and emitted >= limit:
                            break
                    if limit is not None and emitted >= limit:
                        break
                if limit is not None and emitted >= limit:
                    break
            if buffered:
                writer.write_table(pa.Table.from_pylist(buffered, schema=QUALITY_SCHEMA))
            connection.commit()
            writer.close()
            del writers[source.source_id]
        connection.close()
        for source_name, temporary in temporary_outputs.items():
            temporary.replace(outputs[source_name])
    except Exception:
        for writer in writers.values():
            writer.close()
        for temporary in temporary_outputs.values():
            temporary.unlink(missing_ok=True)
        raise
    finally:
        if executor is not None:
            executor.shutdown(cancel_futures=True)
        if dedup_path is not None:
            dedup_path.unlink(missing_ok=True)

    summary = {
        "generated_at": utc_now(),
        "source_id": source_id,
        "limit_per_source": limit,
        "workers": workers,
        "priority_order": [source.source_id for source in sources],
        "sources": {name: dict(sorted(counts.items())) for name, counts in summary_counts.items()},
    }
    summary_path = quality_dir / "summary.json"
    temporary_summary = summary_path.with_name(f".{summary_path.name}.{uuid4().hex}.tmp")
    temporary_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temporary_summary.replace(summary_path)
    return summary_path


def analyze_text(text: str, provenance_class: str) -> dict[str, Any]:
    characters = len(text)
    words = text.split()
    letters = [character for character in text if character.isalpha()]
    devanagari_ratio = sum("\u0900" <= character <= "\u097f" for character in letters) / len(letters) if letters else 0.0
    latin_ratio = sum(("a" <= character.lower() <= "z") for character in letters) / len(letters) if letters else 0.0
    replacement_count = text.count("\ufffd")
    control_count = sum(unicodedata.category(character) == "Cc" and not character.isspace() for character in text)
    word_counts = Counter(words)
    dominant_token_ratio = max(word_counts.values(), default=0) / len(words) if words else 0.0

    flags: list[str] = []
    if characters < 40:
        flags.append("short_document")
    if devanagari_ratio < 0.65:
        flags.append("low_devanagari_ratio")
    if latin_ratio > 0.15:
        flags.append("latin_contamination")
    if replacement_count:
        flags.append("replacement_character")
    if control_count:
        flags.append("control_character")
    if dominant_token_ratio > 0.12 and len(words) >= 20:
        flags.append("high_token_repetition")

    score = 0.65 * devanagari_ratio
    score += 0.15 * (1.0 - min(1.0, latin_ratio * 2.0))
    score += 0.1 if replacement_count == 0 else 0.0
    score += 0.1 * (1.0 - min(1.0, dominant_token_ratio * 4.0))
    quality_score = max(0.0, min(1.0, score))

    if provenance_class == "synthetic_translation":
        tier = "synthetic_translation"
    elif characters >= 100 and quality_score >= 0.85:
        tier = "general_clean"
    elif quality_score >= 0.6:
        tier = "ocr_recoverable"
    else:
        tier = "quarantine"
    return {
        "character_count": characters,
        "word_count": len(words),
        "devanagari_ratio": devanagari_ratio,
        "latin_ratio": latin_ratio,
        "replacement_count": replacement_count,
        "control_count": control_count,
        "dominant_token_ratio": dominant_token_ratio,
        "quality_score": quality_score,
        "curriculum_tier": tier,
        "quality_flags": flags,
    }


def _analyze_and_hash(job: tuple[str, str]) -> tuple[str, str, dict[str, Any]]:
    raw_text, provenance_class = job
    text = _normalize_text(raw_text)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return text, digest, analyze_text(text, provenance_class)


def _select_sources(source_id: str) -> tuple[QualitySource, ...]:
    if source_id == "all":
        return SANGRAHA_QUALITY_SOURCES
    selected = tuple(source for source in SANGRAHA_QUALITY_SOURCES if source.source_id == source_id)
    if not selected:
        known = ", ".join(source.source_id for source in SANGRAHA_QUALITY_SOURCES)
        raise ValueError(f"unknown quality source '{source_id}'. Known sources: {known}")
    return selected


def _normalize_text(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).replace("\ufeff", "").split())
