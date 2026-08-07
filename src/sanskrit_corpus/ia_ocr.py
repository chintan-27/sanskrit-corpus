from __future__ import annotations

import gzip
import hashlib
import json
import os
import tempfile
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .internet_archive import DEFAULT_IA_QUERY, _safe_component, item_metadata, load_census_items, search_items
from .manifest import append_jsonl, utc_now
from .sources import download_file


class OcrBackend(Protocol):
    name: str

    def recognize_pdf(self, path: Path) -> tuple[str, list[float]]: ...


@dataclass(frozen=True)
class IaOcrResult:
    item_count: int
    ocr_count: int
    skipped_count: int
    failed_count: int
    manifest_path: str


class PaddleDevanagariBackend:
    name = "paddleocr_pp-ocrv5_devanagari"

    def __init__(self) -> None:
        from paddleocr import PaddleOCR  # type: ignore[import-not-found]

        self._pipeline = PaddleOCR(
            lang="sa",
            ocr_version="PP-OCRv5",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )

    def recognize_pdf(self, path: Path) -> tuple[str, list[float]]:
        pages: list[str] = []
        scores: list[float] = []
        for page_number, result in enumerate(self._pipeline.predict(str(path)), start=1):
            payload = result.json
            if callable(payload):
                payload = payload()
            data = payload.get("res", payload) if isinstance(payload, dict) else {}
            texts = data.get("rec_texts", []) if isinstance(data, dict) else []
            page_scores = data.get("rec_scores", []) if isinstance(data, dict) else []
            pages.append(f"\n\n<<<PAGE {page_number}>>>\n" + "\n".join(str(text) for text in texts))
            scores.extend(float(score) for score in page_scores)
        return "".join(pages).strip(), scores


def pull_and_ocr_internet_archive(
    root: Path,
    query: str = DEFAULT_IA_QUERY,
    limit: int | None = None,
    shard_count: int = 1,
    shard_index: int = 0,
    missing_ocr_only: bool = False,
    backend: OcrBackend | None = None,
    catalog_path: Path | None = None,
) -> IaOcrResult:
    if shard_count < 1 or not 0 <= shard_index < shard_count:
        raise ValueError("shard_index must be between zero and shard_count - 1")
    target_root = root / "data" / "raw" / "internet_archive"
    manifest_path = root / "data" / "manifests" / f"internet_archive_ocr_shard_{shard_index:03d}.jsonl"
    target_root.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    recognizer = backend or PaddleDevanagariBackend()
    items = load_census_items(catalog_path, require_pdf_without_ocr=True) if catalog_path else search_items(query, limit)
    selected_items = items[:limit] if limit is not None else items
    items = selected_items[shard_index::shard_count]
    item_count = ocr_count = skipped_count = failed_count = 0

    scratch_parent_value = os.environ.get("SLURM_TMPDIR") or os.environ.get("TMPDIR")
    scratch_parent = Path(scratch_parent_value) if scratch_parent_value else None
    for item in items:
        identifier = _safe_component(str(item["identifier"]))
        item_count += 1
        item_dir = target_root / identifier
        output_path = item_dir / "_paddleocr_v5_sa.txt.gz"
        if output_path.exists():
            skipped_count += 1
            continue
        try:
            metadata = _load_or_fetch_metadata(item_dir, identifier)
            files = metadata.get("files", [])
            if missing_ocr_only and _has_ocr_text(files):
                skipped_count += 1
                continue
            pdf = select_pdf_for_ocr(files)
            if pdf is None:
                skipped_count += 1
                continue
            with tempfile.TemporaryDirectory(prefix="sanskrit-ia-ocr-", dir=scratch_parent) as temporary:
                pdf_path = Path(temporary) / "source.pdf"
                url = f"https://archive.org/download/{urllib.parse.quote(identifier)}/{urllib.parse.quote(str(pdf['name']))}"
                download = download_file(url, pdf_path, timeout=900)
                text, scores = recognizer.recognize_pdf(pdf_path)
                if not text.strip():
                    raise RuntimeError("OCR returned no text")
                item_dir.mkdir(parents=True, exist_ok=True)
                _write_gzip_text(output_path, text)
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            ocr_count += 1
            row = {
                "source_id": "internet_archive",
                "identifier": identifier,
                "status": "ok_ocr",
                "ocr_engine": recognizer.name,
                "source_file": pdf["name"],
                "source_bytes": download.byte_count,
                "local_path": str(output_path),
                "text_sha256": digest,
                "mean_confidence": sum(scores) / len(scores) if scores else None,
                "line_count": len(text.splitlines()),
                "ocr_at": utc_now(),
                "release_status": "needs_audit",
            }
        except Exception as exc:
            failed_count += 1
            row = {
                "source_id": "internet_archive",
                "identifier": identifier,
                "status": f"failed:{type(exc).__name__}:{exc}",
                "ocr_engine": recognizer.name,
                "ocr_at": utc_now(),
                "release_status": "needs_audit",
            }
        append_jsonl(manifest_path, [row])
    return IaOcrResult(item_count, ocr_count, skipped_count, failed_count, str(manifest_path))


def select_pdf_for_ocr(files: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [file for file in files if str(file.get("name", "")).lower().endswith(".pdf")]
    if not candidates:
        return None
    return max(candidates, key=lambda file: (file.get("source") == "original", int(file.get("size") or 0)))


def _has_ocr_text(files: list[dict[str, Any]]) -> bool:
    return any(str(file.get("name", "")).lower().endswith(("_djvu.txt", "_text.txt")) for file in files)


def _load_or_fetch_metadata(item_dir: Path, identifier: str) -> dict[str, Any]:
    path = item_dir / "_metadata.json"
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    payload = item_metadata(identifier)
    item_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _write_gzip_text(path: Path, text: str) -> None:
    temporary = path.with_name(f"{path.name}.partial")
    with gzip.open(temporary, "wt", encoding="utf-8", compresslevel=6) as output:
        output.write(text)
    with gzip.open(temporary, "rt", encoding="utf-8") as verification:
        if verification.read() != text:
            temporary.unlink(missing_ok=True)
            raise RuntimeError("gzip verification failed")
    temporary.replace(path)
