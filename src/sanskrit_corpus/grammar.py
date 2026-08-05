from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq

from .manifest import file_stats, utc_now

GRAMMAR_SOURCES = ("ud_sanskrit_vedic", "github_oliverhellwig")

TOKEN_SCHEMA = pa.struct(
    [
        ("form", pa.string()),
        ("form_latn", pa.string()),
        ("lemma", pa.string()),
        ("lemma_latn", pa.string()),
        ("unsandhied", pa.string()),
        ("unsandhied_latn", pa.string()),
        ("upos", pa.string()),
        ("xpos", pa.string()),
        ("feats", pa.map_(pa.string(), pa.string())),
        ("head", pa.string()),
        ("deprel", pa.string()),
    ]
)

GRAMMAR_SCHEMA = pa.schema(
    [
        ("record_id", pa.string()),
        ("source_id", pa.string()),
        ("split", pa.string()),
        ("text", pa.string()),
        ("text_latn", pa.string()),
        ("source_path", pa.string()),
        ("title", pa.string()),
        ("chapter", pa.string()),
        ("content_sha256", pa.string()),
        ("token_count", pa.int32()),
        ("tokens", pa.list_(TOKEN_SCHEMA)),
        ("surface_sequence", pa.list_(pa.string())),
        ("unsandhied_sequence", pa.list_(pa.string())),
        ("lemma_sequence", pa.list_(pa.string())),
        ("morph_sequence", pa.list_(pa.string())),
    ]
)


def build_grammar_verified(root: Path, force: bool = False) -> Path:
    inputs = {source: root / "data" / "processed" / f"{source}.jsonl" for source in GRAMMAR_SOURCES}
    missing = [path for path in inputs.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing processed grammar source: {missing[0]}")

    output_dir = root / "data" / "grammar"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "grammar_verified.parquet"
    manifest_path = output_dir / "manifest.json"
    if output.exists() and not force:
        raise FileExistsError(f"{output} already exists; pass --force to replace it")

    temporary = output.with_name(f".{output.name}.{uuid4().hex}.tmp")
    writer = pq.ParquetWriter(temporary, GRAMMAR_SCHEMA, compression="zstd")
    counts: Counter[str] = Counter()
    buffered: list[dict[str, Any]] = []
    dedup_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="sanskrit-grammar-dedup-", suffix=".sqlite3", dir=output_dir, delete=False) as handle:
            dedup_path = Path(handle.name)
        connection = sqlite3.connect(dedup_path)
        connection.execute("PRAGMA synchronous=OFF")
        connection.execute("PRAGMA journal_mode=OFF")
        connection.execute("CREATE TABLE content (content_sha256 TEXT PRIMARY KEY, record_id TEXT NOT NULL)")
        for source_id in GRAMMAR_SOURCES:
            with inputs[source_id].open(encoding="utf-8") as handle:
                for line in handle:
                    row = json.loads(line)
                    converted = _convert_record(row)
                    digest = str(converted["content_sha256"])
                    cursor = connection.execute("INSERT OR IGNORE INTO content VALUES (?, ?)", (digest, converted["record_id"]))
                    if cursor.rowcount == 0:
                        counts["duplicates_excluded"] += 1
                        counts[f"source:{source_id}:duplicates_excluded"] += 1
                        continue
                    buffered.append(converted)
                    split = str(converted["split"])
                    counts["records"] += 1
                    counts["tokens"] += int(converted["token_count"])
                    counts[f"source:{source_id}:records"] += 1
                    counts[f"source:{source_id}:tokens"] += int(converted["token_count"])
                    counts[f"split:{split}:records"] += 1
                    if len(buffered) >= 2048:
                        writer.write_table(pa.Table.from_pylist(buffered, schema=GRAMMAR_SCHEMA))
                        buffered = []
                        connection.commit()
        if buffered:
            writer.write_table(pa.Table.from_pylist(buffered, schema=GRAMMAR_SCHEMA))
        connection.close()
        writer.close()
        temporary.replace(output)
    except Exception:
        writer.close()
        temporary.unlink(missing_ok=True)
        raise
    finally:
        if dedup_path is not None:
            dedup_path.unlink(missing_ok=True)

    byte_count, checksum = file_stats(output)
    manifest = {
        "created_at": utc_now(),
        "artifact": str(output.relative_to(root)),
        "byte_count": byte_count,
        "checksum_sha256": checksum,
        "dedup_priority": list(GRAMMAR_SOURCES),
        "dcs_split_policy": "sha256(title) bucket: train 0-9799, dev 9800-9899, test 9900-9999",
        "counts": dict(sorted(counts.items())),
        "license_note": "Mixed CC BY-SA 4.0 and CC BY 4.0; retain source-level attribution when distributing.",
    }
    manifest_temporary = manifest_path.with_name(f".{manifest_path.name}.{uuid4().hex}.tmp")
    manifest_temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    manifest_temporary.replace(manifest_path)
    return manifest_path


def _convert_record(row: dict[str, Any]) -> dict[str, Any]:
    source_id = str(row["source_id"])
    title = str(row.get("title") or "") or None
    split = str(row.get("split") or _dcs_split(str(title or row["source_path"])))
    tokens = [_convert_token(token) for token in row.get("tokens", [])]
    text = str(row["text"])
    return {
        "record_id": str(row["record_id"]),
        "source_id": source_id,
        "split": split,
        "text": text,
        "text_latn": str(row.get("text_latn") or ""),
        "source_path": str(row["source_path"]),
        "title": title,
        "chapter": str(row.get("chapter") or row.get("citation_chapter") or "") or None,
        "content_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "token_count": len(tokens),
        "tokens": tokens,
        "surface_sequence": [str(token["form"]) for token in tokens],
        "unsandhied_sequence": [str(token["unsandhied"] or token["form"]) for token in tokens],
        "lemma_sequence": [str(token["lemma"] or token["form"]) for token in tokens],
        "morph_sequence": [_morph_token(token) for token in tokens],
    }


def _convert_token(token: dict[str, Any]) -> dict[str, Any]:
    return {
        "form": str(token.get("form") or ""),
        "form_latn": str(token.get("form_latn") or ""),
        "lemma": token.get("lemma"),
        "lemma_latn": token.get("lemma_latn"),
        "unsandhied": token.get("unsandhied"),
        "unsandhied_latn": token.get("unsandhied_latn"),
        "upos": str(token.get("upos") or "_"),
        "xpos": str(token.get("xpos") or "_"),
        "feats": dict(token.get("feats") or {}),
        "head": str(token.get("head") or "_"),
        "deprel": str(token.get("deprel") or "_"),
    }


def _morph_token(token: dict[str, Any]) -> str:
    lemma = str(token["lemma"] or token["form"])
    attributes = [str(token["upos"])]
    attributes.extend(f"{key}={value}" for key, value in sorted(token["feats"].items()))
    return f"{lemma}<{'|'.join(attributes)}>"


def _dcs_split(work_key: str) -> str:
    bucket = int(hashlib.sha256(work_key.encode("utf-8")).hexdigest()[:8], 16) % 10_000
    if bucket < 9800:
        return "train"
    if bucket < 9900:
        return "dev"
    return "test"
