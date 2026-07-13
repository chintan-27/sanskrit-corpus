from pathlib import Path

from sanskrit_corpus.licensing import resolve_license


def test_sarit_license_is_resolved_per_tei_document(tmp_path: Path) -> None:
    raw = tmp_path / "data" / "raw" / "sarit_corpus"
    raw.mkdir(parents=True)
    (raw / "licensed.xml").write_text(
        '<TEI><teiHeader><availability><licence><ref target="https://creativecommons.org/licenses/by-sa/4.0/">CC</ref></licence></availability></teiHeader></TEI>',
        encoding="utf-8",
    )

    decision = resolve_license(tmp_path, {"source_id": "sarit_corpus", "source_path": "licensed.xml"})

    assert decision.license_label == "CC-BY-SA-4.0"
    assert decision.release_status == "releasable"


def test_sarit_without_evidence_remains_quarantined(tmp_path: Path) -> None:
    decision = resolve_license(tmp_path, {"source_id": "sarit_corpus", "source_path": "unknown.xml"})

    assert decision.release_status == "needs_audit"
