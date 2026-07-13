import json
from pathlib import Path

from sanskrit_corpus.validation import validate_processed


def _row(record_id: str) -> dict[str, object]:
    return {
        "record_id": record_id,
        "source_id": "fixture",
        "record_type": "text",
        "text": "रामः वनं गच्छति।",
        "text_lang": "sa-Deva",
        "license_label": "Apache-2.0",
        "release_status": "releasable",
        "source_url": "https://example.test",
        "source_path": "fixture.txt",
        "normalization": ["unicode_nfc"],
    }


def test_validation_accepts_legacy_rows_with_warning(tmp_path: Path) -> None:
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    (processed / "fixture.jsonl").write_text(json.dumps(_row("one"), ensure_ascii=False) + "\n", encoding="utf-8")

    report = validate_processed(tmp_path)

    assert report["status"] == "ok"
    assert report["counts"]["warning:legacy_provenance"] == 1


def test_validation_rejects_duplicate_ids(tmp_path: Path) -> None:
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    row = json.dumps(_row("duplicate"), ensure_ascii=False)
    (processed / "fixture.jsonl").write_text(f"{row}\n{row}\n", encoding="utf-8")

    report = validate_processed(tmp_path, max_errors=1)

    assert report["status"] == "failed"
    assert report["counts"]["error:duplicate_record_id"] == 1
    assert report["examples"] == [
        {
            "level": "error",
            "code": "duplicate_record_id",
            "path": str(processed / "fixture.jsonl"),
            "line_number": 2,
            "message": "duplicate",
        }
    ]
