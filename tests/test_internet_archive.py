import json
from pathlib import Path

import pytest

from sanskrit_corpus.internet_archive import (
    _bounded_local_path,
    compact_internet_archive,
    compact_text_file,
    item_metadata,
    load_census_items,
    pull_internet_archive,
    search_items,
    select_files,
)
from sanskrit_corpus.sources import DownloadResult


def test_select_files_for_ocr_text() -> None:
    files = [{"name": "book_djvu.txt"}, {"name": "book.pdf"}, {"name": "meta.xml"}]

    assert select_files(files, "ocr_text") == [{"name": "book_djvu.txt"}]


def test_select_files_for_all() -> None:
    files = [{"name": "book_djvu.txt"}, {"name": "book.pdf"}, {"name": "book.epub"}, {"name": "meta.xml"}]

    assert len(select_files(files, "all")) == 3


def test_internet_archive_pull_downloads_and_skips_quota(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sanskrit_corpus.internet_archive.search_items", lambda query, limit: [{"identifier": "item"}])
    monkeypatch.setattr(
        "sanskrit_corpus.internet_archive.item_metadata",
        lambda identifier: {"files": [{"name": "book_djvu.txt", "size": "4"}, {"name": "large_text.txt", "size": "999999"}]},
    )

    def fake_download(url: str, destination: Path, **kwargs) -> DownloadResult:
        destination.write_bytes(b"text")
        return DownloadResult(4, "checksum", None, None)

    monkeypatch.setattr("sanskrit_corpus.internet_archive.download_file", fake_download)
    result = pull_internet_archive(tmp_path, limit=1, max_gb=0.000001, file_kind="ocr_text")
    rows = [json.loads(line) for line in Path(result.manifest_path).read_text(encoding="utf-8").splitlines()]

    assert result.file_count == 1
    assert [row["status"] for row in rows] == ["ok", "skipped_quota"]


def test_internet_archive_api_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sanskrit_corpus.internet_archive.fetch_json",
        lambda url, timeout: {"response": {"docs": [{"identifier": "one"}]}} if "advancedsearch" in url else {"files": []},
    )

    assert search_items("sanskrit", 1) == [{"identifier": "one"}]
    assert item_metadata("one") == {"files": []}
    with pytest.raises(ValueError):
        select_files([], "unknown")
    with pytest.raises(ValueError):
        pull_internet_archive(Path("."), limit=-1)


def test_search_items_paginates_without_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter(
        [
            {"response": {"numFound": 2, "docs": [{"identifier": "one"}]}},
            {"response": {"numFound": 2, "docs": [{"identifier": "two"}]}},
        ]
    )
    monkeypatch.setattr("sanskrit_corpus.internet_archive.fetch_json", lambda *args, **kwargs: next(responses))

    assert [item["identifier"] for item in search_items("sanskrit", None)] == ["one", "two"]


def test_compact_text_file_is_lossless_and_removes_source(tmp_path: Path) -> None:
    source = tmp_path / "book_djvu.txt"
    source.write_bytes("संस्कृतम्\n".encode())

    destination, digest = compact_text_file(source)

    import gzip
    import hashlib

    assert not source.exists()
    assert gzip.open(destination, "rb").read() == "संस्कृतम्\n".encode()
    assert digest == hashlib.sha256("संस्कृतम्\n".encode()).hexdigest()


def test_restart_skips_an_existing_compacted_download(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sanskrit_corpus.internet_archive.search_items", lambda query, limit: [{"identifier": "item"}])
    metadata_calls = 0

    def fake_metadata(identifier: str) -> dict[str, object]:
        nonlocal metadata_calls
        metadata_calls += 1
        return {"files": [{"name": "book_djvu.txt", "size": "4"}]}

    monkeypatch.setattr("sanskrit_corpus.internet_archive.item_metadata", fake_metadata)
    item_dir = tmp_path / "data/raw/internet_archive/item"
    item_dir.mkdir(parents=True)
    (item_dir / "book_djvu.txt.gz").write_bytes(b"existing")

    result = pull_internet_archive(tmp_path, limit=1, max_gb=None, file_kind="ocr_text", compact_text=True)
    rows = [json.loads(line) for line in Path(result.manifest_path).read_text(encoding="utf-8").splitlines()]

    assert result.file_count == 1
    assert rows[0]["status"] == "already_compacted"
    assert metadata_calls == 0


def test_compaction_deletes_artifacts_only_after_text_is_preserved(tmp_path: Path) -> None:
    with_text = tmp_path / "data/raw/internet_archive/with_text"
    without_text = tmp_path / "data/raw/internet_archive/without_text"
    with_text.mkdir(parents=True)
    without_text.mkdir(parents=True)
    (with_text / "book_djvu.txt").write_text("संस्कृतम्", encoding="utf-8")
    (with_text / "book.pdf").write_bytes(b"pdf")
    (with_text / "_metadata.json").write_text("{}", encoding="utf-8")
    (without_text / "book.pdf").write_bytes(b"pdf")

    result = compact_internet_archive(tmp_path, delete_source_artifacts=True)

    assert result.text_file_count == 1
    assert (with_text / "book_djvu.txt.gz").exists()
    assert not (with_text / "book.pdf").exists()
    assert (with_text / "_metadata.json").exists()
    assert (without_text / "book.pdf").exists()


def test_load_census_items_filters_ocr_and_missing_ocr_pdf(tmp_path: Path) -> None:
    path = tmp_path / "census.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"identifier": "ocr", "has_ocr": True, "has_usable_pdf": True}),
                json.dumps({"identifier": "missing", "has_ocr": False, "has_usable_pdf": True}),
                json.dumps({"identifier": "neither", "has_ocr": False, "has_usable_pdf": False}),
            ]
        ),
        encoding="utf-8",
    )

    assert [item["identifier"] for item in load_census_items(path, require_ocr=True)] == ["ocr"]
    assert [item["identifier"] for item in load_census_items(path, require_pdf_without_ocr=True)] == ["missing"]


def test_bounded_local_path_handles_pathological_dotted_names(tmp_path: Path) -> None:
    name = ".".join(["segment"] * 100) + "_djvu.txt"

    result = _bounded_local_path(tmp_path, name)

    assert len(result.name.encode("utf-8")) <= 180
    assert result.suffix == ".txt"


def test_completed_index_skips_metadata_and_manifest_io(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    catalog = tmp_path / "census.jsonl"
    catalog.write_text(json.dumps({"identifier": "done", "has_ocr": True}) + "\n", encoding="utf-8")
    completed = tmp_path / "completed.txt"
    completed.write_text("done\n", encoding="utf-8")

    def unexpected_metadata(identifier: str) -> dict[str, object]:
        raise AssertionError("metadata should not be requested for a completed item")

    monkeypatch.setattr("sanskrit_corpus.internet_archive.item_metadata", unexpected_metadata)
    result = pull_internet_archive(
        tmp_path,
        limit=None,
        max_gb=None,
        compact_text=True,
        catalog_path=catalog,
        completed_index_path=completed,
    )

    assert result.item_count == 1
    assert result.file_count == 1
    assert not Path(result.manifest_path).exists()
