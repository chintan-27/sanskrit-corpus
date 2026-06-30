from __future__ import annotations

import csv
import json
import sys
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .manifest import append_jsonl
from .sources import build_sources


csv.field_size_limit(sys.maxsize)


@dataclass(frozen=True)
class ProcessResult:
    source_id: str
    status: str
    output_path: str
    record_count: int
    error: str | None = None


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text)
    return " ".join(normalized.replace("\ufeff", "").split())


def process_sources(root: Path, source_id: str = "all", force: bool = False, limit: int | None = None) -> list[ProcessResult]:
    processors = {
        "itihasa": process_itihasa,
        "ud_sanskrit_vedic": process_ud_sanskrit_vedic,
        "naamah": process_naamah,
        "samhitika_0_0_1": process_samhitika,
    }
    selected = list(processors) if source_id == "all" else [source_id]
    results: list[ProcessResult] = []
    for selected_id in selected:
        processor = processors.get(selected_id)
        if processor is None:
            results.append(ProcessResult(selected_id, "skipped", "", 0, "no processor is available for this source"))
            continue
        try:
            results.append(processor(root, force=force, limit=limit))
        except Exception as exc:
            results.append(ProcessResult(selected_id, "failed", "", 0, str(exc)))
    return results


def _output_path(root: Path, source_id: str, force: bool) -> Path:
    output = root / "data" / "processed" / f"{source_id}.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not force:
        raise FileExistsError(f"{output} already exists; pass --force to replace it")
    output.write_text("", encoding="utf-8")
    return output


def _source_metadata(source_id: str) -> dict[str, str]:
    record = build_sources()[source_id].record
    return {
        "license_label": record.license_label,
        "release_status": record.release_status,
        "source_url": record.url,
    }


def process_itihasa(root: Path, force: bool = False, limit: int | None = None) -> ProcessResult:
    source_id = "itihasa"
    raw_dir = root / "data" / "raw" / source_id
    output = _output_path(root, source_id, force)
    metadata = _source_metadata(source_id)
    count = 0

    for split in ("train", "dev", "test"):
        sn_path = raw_dir / f"{split}.sn.csv"
        en_path = raw_dir / f"{split}.en.csv"
        if not sn_path.exists() or not en_path.exists():
            continue
        rows = []
        with sn_path.open(encoding="utf-8", newline="") as sn_file, en_path.open(encoding="utf-8", newline="") as en_file:
            for line_number, (sn_row, en_row) in enumerate(zip(csv.reader(sn_file), csv.reader(en_file)), start=1):
                sanskrit = normalize_text(sn_row[0]) if sn_row else ""
                english = normalize_text(en_row[0]) if en_row else ""
                if not sanskrit:
                    continue
                count += 1
                rows.append(
                    {
                        "record_id": f"{source_id}:{split}:{line_number}",
                        "source_id": source_id,
                        "record_type": "parallel_sentence",
                        "split": split,
                        "text": sanskrit,
                        "text_lang": "sa",
                        "translation": english,
                        "translation_lang": "en",
                        "source_path": f"{split}.sn.csv",
                        "line_number": line_number,
                        "normalization": ["unicode_nfc", "whitespace_squeeze"],
                        **metadata,
                    }
                )
                if limit is not None and count >= limit:
                    append_jsonl(output, rows)
                    return ProcessResult(source_id, "ok", str(output), count)
        append_jsonl(output, rows)

    return ProcessResult(source_id, "ok", str(output), count)


def process_ud_sanskrit_vedic(root: Path, force: bool = False, limit: int | None = None) -> ProcessResult:
    source_id = "ud_sanskrit_vedic"
    raw_dir = root / "data" / "raw" / source_id
    output = _output_path(root, source_id, force)
    metadata = _source_metadata(source_id)
    count = 0

    for split in ("train", "dev", "test"):
        path = raw_dir / f"sa_vedic-ud-{split}.conllu"
        if not path.exists():
            continue
        rows = []
        for sentence in _read_conllu_sentences(path):
            text = normalize_text(sentence.get("text", ""))
            if not text:
                continue
            count += 1
            sent_id = sentence.get("sent_id", str(count))
            rows.append(
                {
                    "record_id": f"{source_id}:{split}:{sent_id}",
                    "source_id": source_id,
                    "record_type": "treebank_sentence",
                    "split": split,
                    "text": text,
                    "text_lang": "sa-Latn",
                    "sent_id": sent_id,
                    "citation_text": sentence.get("citation_text"),
                    "citation_chapter": sentence.get("citation_chapter"),
                    "source_path": path.name,
                    "normalization": ["unicode_nfc", "whitespace_squeeze"],
                    **metadata,
                }
            )
            if limit is not None and count >= limit:
                append_jsonl(output, rows)
                return ProcessResult(source_id, "ok", str(output), count)
        append_jsonl(output, rows)

    return ProcessResult(source_id, "ok", str(output), count)


def _read_conllu_sentences(path: Path) -> Iterable[dict[str, str]]:
    current: dict[str, str] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line:
                if current:
                    yield current
                    current = {}
                continue
            if line.startswith("# ") and " = " in line:
                key, value = line[2:].split(" = ", 1)
                current[key] = value
        if current:
            yield current


def process_naamah(root: Path, force: bool = False, limit: int | None = None) -> ProcessResult:
    source_id = "naamah"
    raw_path = root / "data" / "raw" / source_id / "Sanskrit_NER_Silver_v1.jsonl"
    output = _output_path(root, source_id, force)
    metadata = _source_metadata(source_id)
    count = 0
    rows = []

    with raw_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            payload = json.loads(line)
            tokens = payload.get("tokens") or []
            text = normalize_text(" ".join(tokens))
            if not text:
                continue
            count += 1
            rows.append(
                {
                    "record_id": f"{source_id}:{line_number}",
                    "source_id": source_id,
                    "record_type": "ner_sentence",
                    "text": text,
                    "text_lang": "sa-Deva",
                    "tokens": tokens,
                    "ner_tags": payload.get("ner_tags"),
                    "source_path": raw_path.name,
                    "line_number": line_number,
                    "normalization": ["unicode_nfc", "whitespace_squeeze"],
                    **metadata,
                }
            )
            if len(rows) >= 5000:
                append_jsonl(output, rows)
                rows = []
            if limit is not None and count >= limit:
                append_jsonl(output, rows)
                return ProcessResult(source_id, "ok", str(output), count)
    append_jsonl(output, rows)

    return ProcessResult(source_id, "ok", str(output), count)


def process_samhitika(root: Path, force: bool = False, limit: int | None = None) -> ProcessResult:
    import pyarrow.parquet as pq

    source_id = "samhitika_0_0_1"
    raw_path = root / "data" / "raw" / source_id / "translations.parquet"
    output = _output_path(root, source_id, force)
    metadata = _source_metadata(source_id)
    count = 0
    rows = []

    parquet = pq.ParquetFile(raw_path)
    for batch in parquet.iter_batches(columns=["bookcorpus_id", "text"], batch_size=5000):
        payload = batch.to_pydict()
        for bookcorpus_id, text_value in zip(payload["bookcorpus_id"], payload["text"]):
            text = normalize_text(text_value or "")
            if not text:
                continue
            count += 1
            rows.append(
                {
                    "record_id": f"{source_id}:{bookcorpus_id if bookcorpus_id is not None else count}",
                    "source_id": source_id,
                    "record_type": "synthetic_translation",
                    "text": text,
                    "text_lang": "sa",
                    "bookcorpus_id": bookcorpus_id,
                    "source_path": raw_path.name,
                    "normalization": ["unicode_nfc", "whitespace_squeeze"],
                    **metadata,
                }
            )
            if len(rows) >= 5000:
                append_jsonl(output, rows)
                rows = []
            if limit is not None and count >= limit:
                append_jsonl(output, rows)
                return ProcessResult(source_id, "ok", str(output), count)
    append_jsonl(output, rows)

    return ProcessResult(source_id, "ok", str(output), count)
