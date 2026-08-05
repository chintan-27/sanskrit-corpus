import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from sanskrit_corpus.quality import analyze_text, profile_sangraha_quality


def _write_partition(root: Path, source_id: str, partition: str, rows: list[dict[str, str]]) -> None:
    raw = root / "data" / "raw" / source_id / partition
    raw.mkdir(parents=True)
    pq.write_table(pa.Table.from_pylist(rows), raw / "part.parquet")


def test_analyze_text_assigns_conservative_tiers() -> None:
    clean = analyze_text("रामः वनं गच्छति। " * 20, "human_source_verified")
    contaminated = analyze_text("This is mostly English text with रामः.", "human_source_verified")
    synthetic = analyze_text("रामः वनं गच्छति। " * 20, "synthetic_translation")

    assert clean["curriculum_tier"] == "general_clean"
    assert contaminated["curriculum_tier"] == "quarantine"
    assert "latin_contamination" in contaminated["quality_flags"]
    assert synthetic["curriculum_tier"] == "synthetic_translation"


def test_profile_quality_marks_cross_partition_duplicates(tmp_path: Path) -> None:
    repeated = "रामः प्रतिदिनं विद्यालयं गच्छति तथा संस्कृतं पठति।"
    _write_partition(
        tmp_path,
        "sangraha_verified_sanskrit",
        "verified/san",
        [{"doc_id": "verified-1", "type": "web", "text": repeated}],
    )
    _write_partition(
        tmp_path,
        "sangraha_unverified_sanskrit",
        "unverified/san",
        [{"doc_id": "unverified-1", "text": repeated}],
    )
    _write_partition(
        tmp_path,
        "sangraha_synthetic_sanskrit_deva",
        "synthetic/san_Deva",
        [{"doc_id": "synthetic-1", "text": "भारतं विशालं राष्ट्रम् अस्ति। " * 5}],
    )

    summary_path = profile_sangraha_quality(tmp_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    unverified = pq.read_table(tmp_path / "data" / "quality" / "sangraha_unverified_sanskrit.parquet").to_pylist()[0]

    assert summary["sources"]["sangraha_unverified_sanskrit"]["duplicates"] == 1
    assert unverified["duplicate"] is True
    assert unverified["curriculum_tier"] == "exact_duplicate"
    assert unverified["duplicate_of"].endswith(":verified-1")
