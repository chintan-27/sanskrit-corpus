from sanskrit_corpus.sources import build_sources


def test_unclear_sources_are_not_releasable() -> None:
    sources = build_sources()

    assert sources["kaggle_sanskrit_text_corpus"].record.release_status == "needs_audit"
    assert sources["aikosh_sanskrit_post_ocr"].record.release_status == "needs_audit"
    assert sources["github_oliverhellwig"].record.release_status == "needs_audit"
    assert sources["gretil_sanskrit"].record.release_status == "needs_audit"
    assert sources["sarit_corpus"].record.release_status == "needs_audit"
    assert sources["saamayik"].record.release_status == "needs_audit"


def test_synthetic_source_is_quarantined() -> None:
    source = build_sources()["samhitika_0_0_1"].record

    assert source.release_status == "synthetic"
    assert source.release_status != "releasable"
