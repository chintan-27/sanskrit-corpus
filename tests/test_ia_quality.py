import gzip
import json
from pathlib import Path

import pytest

from sanskrit_corpus.ia_quality import classify_passage, profile_internet_archive_quality, split_passages


def test_classify_passage_separates_clean_sanskrit_hindi_latin_and_noise() -> None:
    sanskrit = "अथ योगानुशासनम् । योगश्चित्तवृत्तिनिरोधः । तदा द्रष्टुः स्वरूपेऽवस्थानम् । " * 4
    hindi = "यह पुस्तक संस्कृत के विषय में है और इसमें बहुत से उदाहरण दिए गये हैं। " * 5
    latin = "This is an English discussion of Sanskrit literature and its historical development. " * 4
    noise = "॥ # ११ 1 + | $ ३ ॥ # ११ 1 + | $ ३ ॥ # ११ 1 + | $ ३ " * 5

    assert classify_passage(sanskrit)["label"] == "clean_sanskrit_candidate"
    assert classify_passage(hindi)["label"] == "hindi_or_other_devanagari"
    assert classify_passage(latin)["label"] == "english_or_transliteration"
    assert classify_passage(noise)["label"] == "severe_ocr_garbage"


def test_split_passages_respects_page_breaks_and_target_size() -> None:
    passages = list(split_passages("रामः पठति।\fसीता लिखति।", target_chars=100))
    assert passages == ["रामः पठति।", "सीता लिखति।"]


def test_profile_is_resumable_and_preserves_provenance(tmp_path: Path) -> None:
    source = tmp_path / "data/raw/internet_archive/book/book_djvu.txt.gz"
    source.parent.mkdir(parents=True)
    with gzip.open(source, "wt", encoding="utf-8") as output:
        output.write("अथ योगानुशासनम् । योगश्चित्तवृत्तिनिरोधः । " * 5)

    first = profile_internet_archive_quality(tmp_path)
    second = profile_internet_archive_quality(tmp_path)
    sidecar = tmp_path / "data/quality/internet_archive/book/book_djvu.txt.quality.jsonl.gz"
    with gzip.open(sidecar, "rt", encoding="utf-8") as rows:
        row = json.loads(next(rows))

    assert first.files_profiled == 1
    assert second.files_skipped == 1
    assert row["source_document_id"] == "book"
    assert row["release_status"] == "needs_audit"


def test_profile_validates_shard_arguments(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        profile_internet_archive_quality(tmp_path, shard_count=2, shard_index=2)


def test_profile_bounds_long_sidecar_names(tmp_path: Path) -> None:
    source = tmp_path / "data/raw/internet_archive/book" / ("x" * 205 + "_djvu.txt.gz")
    source.parent.mkdir(parents=True)
    with gzip.open(source, "wt", encoding="utf-8") as output:
        output.write("अथ योगानुशासनम् । " * 10)

    result = profile_internet_archive_quality(tmp_path)
    sidecars = list((tmp_path / "data/quality/internet_archive/book").glob("*.quality.jsonl.gz"))

    assert result.files_profiled == 1
    assert len(sidecars) == 1
    assert len(sidecars[0].name.encode()) <= 220
