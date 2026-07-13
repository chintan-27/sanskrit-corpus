import json
from pathlib import Path

import pytest

from sanskrit_corpus.internet_archive import item_metadata, pull_internet_archive, search_items, select_files
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
