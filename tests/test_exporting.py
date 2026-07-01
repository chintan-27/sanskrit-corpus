import json
from pathlib import Path

from sanskrit_corpus.exporting import audit_processed, export_profile, is_clean_record


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
    (processed / "a.jsonl").write_text(
        '{"record_id":"1","release_status":"releasable"}\n'
        '{"record_id":"2","release_status":"synthetic"}\n',
        encoding="utf-8",
    )

    path, count = export_profile(tmp_path, "releasable", force=True)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    assert count == 1
    assert rows[0]["record_id"] == "1"


def test_clean_export_dedupes_and_filters_short_rows(tmp_path: Path) -> None:
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    long_text = "रामः वनं गच्छति। सीता अपि तेन सह गच्छति। लक्ष्मणः तयोः रक्षणं करोति।"
    (processed / "a.jsonl").write_text(
        json.dumps({"record_id": "1", "release_status": "releasable", "text_lang": "sa-Deva", "text": long_text}, ensure_ascii=False) + "\n"
        + json.dumps({"record_id": "2", "release_status": "releasable", "text_lang": "sa-Deva", "text": long_text}, ensure_ascii=False) + "\n"
        + json.dumps({"record_id": "3", "release_status": "releasable", "text_lang": "sa-Deva", "text": "लघु"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    path, count = export_profile(tmp_path, "clean_releasable", force=True)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    assert count == 1
    assert rows[0]["record_id"] == "1"


def test_is_clean_record_rejects_non_devanagari_sanskrit() -> None:
    assert not is_clean_record({"text_lang": "sa-Deva", "text": "This is English text that is long enough to fail the script ratio check."})
