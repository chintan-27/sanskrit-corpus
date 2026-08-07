from __future__ import annotations

import gzip
import hashlib
import json
import re
import unicodedata
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .manifest import utc_now

HINDI_MARKERS = frozenset("और है हैं था थी थे में को से का की के यह वह नहीं गया गयी लिए द्वारा तथा एवं एक".split())
BOILERPLATE_MARKERS = ("copyright", "all rights reserved", "digitized by", "google", "internet archive", "www.", "http")


@dataclass(frozen=True)
class IaQualityResult:
    files_profiled: int
    files_skipped: int
    passages_profiled: int
    summary_path: str


def split_passages(text: str, target_chars: int = 4000) -> Iterator[str]:
    text = unicodedata.normalize("NFC", text).replace("\ufeff", "")
    blocks = re.split(r"\f+|(?:\r?\n\s*){3,}", text)
    for block in blocks:
        lines = [" ".join(line.split()) for line in block.splitlines() if line.strip()]
        buffer: list[str] = []
        length = 0
        for line in lines:
            if buffer and length + len(line) + 1 > target_chars:
                yield "\n".join(buffer)
                buffer, length = [], 0
            buffer.append(line)
            length += len(line) + 1
        if buffer:
            yield "\n".join(buffer)


def classify_passage(text: str) -> dict[str, Any]:
    letters = [character for character in text if character.isalpha()]
    words = re.findall(r"[\w\u0900-\u097f]+", text, flags=re.UNICODE)
    devanagari = sum("\u0900" <= character <= "\u097f" for character in letters)
    latin = sum("a" <= character.lower() <= "z" for character in letters)
    devanagari_ratio = devanagari / len(letters) if letters else 0.0
    latin_ratio = latin / len(letters) if letters else 0.0
    nonspace = [character for character in text if not character.isspace()]
    useful = sum(character.isalpha() or "\u0900" <= character <= "\u097f" for character in nonspace)
    noise_ratio = 1.0 - useful / len(nonspace) if nonspace else 1.0
    normalized_words = [word.strip("।॥").lower() for word in words]
    hindi_hits = sum(word in HINDI_MARKERS for word in normalized_words)
    hindi_marker_ratio = hindi_hits / len(normalized_words) if normalized_words else 0.0
    word_counts = Counter(normalized_words)
    repetition_ratio = max(word_counts.values(), default=0) / len(normalized_words) if normalized_words else 0.0
    replacement_count = text.count("\ufffd") + text.count("\x00")
    danda_count = text.count("।") + text.count("॥")
    danda_ratio = danda_count / max(1, len(words))
    lower = text.lower()

    flags: list[str] = []
    if len(text) < 80:
        flags.append("short")
    if replacement_count:
        flags.append("invalid_characters")
    if noise_ratio > 0.22:
        flags.append("high_symbol_noise")
    if repetition_ratio > 0.15 and len(words) >= 20:
        flags.append("high_repetition")
    if latin_ratio > 0.25:
        flags.append("latin_content")
    if devanagari_ratio < 0.45:
        flags.append("low_devanagari")
    if hindi_marker_ratio > 0.025:
        flags.append("hindi_markers")

    if len(text) < 80 or any(marker in lower for marker in BOILERPLATE_MARKERS):
        label = "front_matter_or_boilerplate"
    elif replacement_count or noise_ratio > 0.32 or (repetition_ratio > 0.25 and noise_ratio > 0.15 and len(words) >= 20):
        label = "severe_ocr_garbage"
    elif latin_ratio >= 0.50:
        label = "english_or_transliteration"
    elif devanagari_ratio < 0.65:
        label = "uncertain_mixed_script"
    elif hindi_marker_ratio > 0.025:
        label = "hindi_or_other_devanagari"
    elif noise_ratio <= 0.10 and devanagari_ratio >= 0.90 and (danda_ratio >= 0.005 or "ः" in text):
        label = "clean_sanskrit_candidate"
    elif noise_ratio <= 0.22 and devanagari_ratio >= 0.75:
        label = "sanskrit_candidate_minor_ocr"
    else:
        label = "uncertain_devanagari"

    score = 0.65 * devanagari_ratio + 0.20 * (1.0 - min(1.0, noise_ratio * 2.5)) + 0.15 * (1.0 - latin_ratio)
    if hindi_marker_ratio > 0.025:
        score -= 0.2
    return {
        "label": label,
        "quality_score": max(0.0, min(1.0, score)),
        "character_count": len(text),
        "word_count": len(words),
        "devanagari_ratio": devanagari_ratio,
        "latin_ratio": latin_ratio,
        "noise_ratio": noise_ratio,
        "hindi_marker_ratio": hindi_marker_ratio,
        "repetition_ratio": repetition_ratio,
        "replacement_count": replacement_count,
        "danda_ratio": danda_ratio,
        "flags": flags,
    }


def profile_internet_archive_quality(
    root: Path, limit: int | None = None, force: bool = False, shard_count: int = 1, shard_index: int = 0
) -> IaQualityResult:
    if shard_count < 1 or not 0 <= shard_index < shard_count:
        raise ValueError("shard_index must be between zero and shard_count - 1")
    raw_root = root / "data/raw/internet_archive"
    output_root = root / "data/quality/internet_archive"
    output_root.mkdir(parents=True, exist_ok=True)
    paths = sorted(raw_root.glob("*/*.txt.gz"))
    if limit is not None:
        paths = paths[:limit]
    paths = paths[shard_index::shard_count]
    totals: Counter[str] = Counter()
    files_profiled = files_skipped = passages_profiled = 0
    for source_path in paths:
        relative = source_path.relative_to(raw_root)
        output_path = _quality_output_path(output_root, relative)
        if output_path.exists() and not force:
            files_skipped += 1
            continue
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = output_path.with_name(f".{uuid4().hex}.tmp")
        seen: set[str] = set()
        try:
            with gzip.open(source_path, "rt", encoding="utf-8", errors="replace") as source, gzip.open(
                temporary, "wt", encoding="utf-8"
            ) as destination:
                for passage_index, passage in enumerate(split_passages(source.read())):
                    digest = hashlib.sha256(passage.encode()).hexdigest()
                    analysis = classify_passage(passage)
                    duplicate = digest in seen
                    seen.add(digest)
                    if duplicate:
                        analysis["label"] = "exact_duplicate"
                        analysis["flags"] = [*analysis["flags"], "exact_duplicate"]
                    row = {
                        "record_id": f"internet_archive:{relative.as_posix()}:{passage_index}",
                        "source_id": "internet_archive",
                        "source_path": relative.as_posix(),
                        "source_document_id": relative.parts[0],
                        "passage_index": passage_index,
                        "content_sha256": digest,
                        "duplicate_within_document": duplicate,
                        "provenance_class": "human_source_ocr",
                        "release_status": "needs_audit",
                        **analysis,
                    }
                    destination.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                    totals[f"label:{row['label']}"] += 1
                    passages_profiled += 1
            temporary.replace(output_path)
            files_profiled += 1
        except Exception:
            temporary.unlink(missing_ok=True)
            totals["failed_files"] += 1
    summary = {
        "generated_at": utc_now(),
        "source_id": "internet_archive",
        "files_discovered": len(paths),
        "files_profiled": files_profiled,
        "files_skipped": files_skipped,
        "passages_profiled": passages_profiled,
        "counts": dict(sorted(totals.items())),
        "method": "conservative_heuristic_v1",
        "shard_count": shard_count,
        "shard_index": shard_index,
        "warning": "Candidate language labels require validation before training export.",
    }
    summary_name = "internet_archive_summary.json" if shard_count == 1 else f"internet_archive_summary_shard_{shard_index:03d}.json"
    summary_path = root / "data/quality" / summary_name
    temporary_summary = summary_path.with_name(f".{summary_path.name}.{uuid4().hex}.tmp")
    temporary_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temporary_summary.replace(summary_path)
    return IaQualityResult(files_profiled, files_skipped, passages_profiled, str(summary_path))


def _quality_output_path(output_root: Path, source_relative: Path) -> Path:
    filename = source_relative.with_suffix(".quality.jsonl.gz").name
    if len(filename.encode()) > 220:
        digest = hashlib.sha256(source_relative.name.encode()).hexdigest()[:24]
        filename = f"{digest}.quality.jsonl.gz"
    return output_root / source_relative.parent / filename
