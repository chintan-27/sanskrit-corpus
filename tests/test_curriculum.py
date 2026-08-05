import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from sanskrit_corpus.curriculum import build_curriculum_manifests
from sanskrit_corpus.quality import QUALITY_SCHEMA


def _quality_row(record_id: str, tier: str, score: float, flags: list[str], provenance: str = "human_source_verified") -> dict:
    return {
        "record_id": record_id,
        "source_id": "source",
        "source_path": "part.parquet",
        "source_document_id": record_id,
        "corpus_partition": "verified/san",
        "provenance_class": provenance,
        "content_sha256": record_id.zfill(64),
        "duplicate": tier == "exact_duplicate",
        "duplicate_of": None,
        "character_count": 200,
        "word_count": 40,
        "devanagari_ratio": 1.0,
        "latin_ratio": 0.0,
        "replacement_count": 0,
        "control_count": 0,
        "dominant_token_ratio": 0.05,
        "quality_score": score,
        "curriculum_tier": tier,
        "quality_flags": flags,
    }


def test_build_curriculum_creates_disjoint_training_phases(tmp_path: Path) -> None:
    quality = tmp_path / "data" / "quality"
    quality.mkdir(parents=True)
    rows = [
        _quality_row("1", "general_clean", 0.97, []),
        _quality_row("2", "general_clean", 0.91, []),
        _quality_row("3", "ocr_recoverable", 0.70, ["replacement_character"]),
        _quality_row("4", "synthetic_translation", 0.90, [], "synthetic_translation"),
        _quality_row("5", "quarantine", 0.30, ["low_devanagari_ratio"]),
        _quality_row("6", "exact_duplicate", 0.99, ["exact_duplicate"]),
    ]
    pq.write_table(pa.Table.from_pylist(rows, schema=QUALITY_SCHEMA), quality / "sangraha_test.parquet")

    manifest_path = build_curriculum_manifests(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    counts = {profile["name"]: profile["record_count"] for profile in manifest["profiles"]}

    assert counts == {
        "phase_1_grammar_candidates": 1,
        "phase_2_verified_clean": 1,
        "phase_3_ocr_recoverable": 1,
        "phase_4_synthetic": 1,
        "excluded_quarantine": 1,
        "excluded_duplicates": 1,
    }
    assert manifest["grammar_verification_status"] == "candidate_only"
    with pytest.raises(FileExistsError):
        build_curriculum_manifests(tmp_path)


def test_build_curriculum_requires_quality_sidecars(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        build_curriculum_manifests(tmp_path)
