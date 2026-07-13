import json
from pathlib import Path

from sanskrit_corpus.exporting import audit_processed, export_profile, is_clean_record


def _record(record_id: str, status: str, text: str = "रामः वनं गच्छति।") -> dict[str, object]:
    return {
        "record_id": record_id,
        "source_id": "a",
        "record_type": "text",
        "text": text,
        "text_lang": "sa-Deva",
        "license_label": "Apache-2.0",
        "release_status": status,
        "source_url": "https://example.test",
        "source_path": "fixture.txt",
        "normalization": ["unicode_nfc"],
    }


def test_audit_processed_counts_statuses(tmp_path: Path) -> None:
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    (processed / "a.jsonl").write_text(
        '{"release_status":"releasable","license_label":"Apache-2.0"}\n'
        '{"release_status":"needs_audit","license_label":"needs_audit"}\n',
        encoding="utf-8",
    )

    report = audit_processed(tmp_path)

    assert report["by_status"] == {"needs_audit": 1, "releasable": 1}
    assert report["by_source"]["a"]["releasable"] == 1


def test_export_profile_filters_by_release_status(tmp_path: Path) -> None:
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    rows = [_record("1", "releasable"), _record("2", "synthetic")]
    (processed / "a.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")

    path, count = export_profile(tmp_path, "releasable", force=True)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    assert count == 1
    assert rows[0]["record_id"] == "1"


def test_clean_export_dedupes_and_filters_short_rows(tmp_path: Path) -> None:
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    long_text = "रामः वनं गच्छति। सीता अपि तेन सह गच्छति। लक्ष्मणः तयोः रक्षणं करोति।"
    rows = [_record("1", "releasable", long_text), _record("2", "releasable", long_text), _record("3", "releasable", "लघु")]
    (processed / "a.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")

    path, count = export_profile(tmp_path, "clean_releasable", force=True)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    assert count == 1
    assert rows[0]["record_id"] == "1"
    assert path.with_suffix(".manifest.json").exists()


def test_export_blocks_invalid_records(tmp_path: Path) -> None:
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    (processed / "a.jsonl").write_text('{"record_id":"broken","release_status":"releasable"}\n', encoding="utf-8")

    try:
        export_profile(tmp_path, "releasable", force=True)
    except ValueError as exc:
        assert "validation errors" in str(exc)
    else:
        raise AssertionError("invalid export was not blocked")


def test_is_clean_record_rejects_non_devanagari_sanskrit() -> None:
    assert not is_clean_record({"text_lang": "sa-Deva", "text": "This is English text that is long enough to fail the script ratio check."})
