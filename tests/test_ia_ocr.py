import gzip
import json
from pathlib import Path

import pytest

from sanskrit_corpus.ia_ocr import PaddleDevanagariBackend, pull_and_ocr_internet_archive, select_pdf_for_ocr
from sanskrit_corpus.sources import DownloadResult


class FakeBackend:
    name = "fake"

    def recognize_pdf(self, path: Path) -> tuple[str, list[float]]:
        assert path.read_bytes() == b"pdf"
        return "संस्कृतम्", [0.9]


def test_select_pdf_prefers_largest_original() -> None:
    files = [
        {"name": "derived.pdf", "source": "derivative", "size": "100"},
        {"name": "small.pdf", "source": "original", "size": "10"},
        {"name": "large.pdf", "source": "original", "size": "20"},
    ]

    assert select_pdf_for_ocr(files) == files[2]


def test_pull_and_ocr_uses_shard_and_removes_temporary_pdf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sanskrit_corpus.ia_ocr.search_items",
        lambda query, limit: [{"identifier": "zero"}, {"identifier": "one"}],
    )
    monkeypatch.setattr(
        "sanskrit_corpus.ia_ocr.item_metadata",
        lambda identifier: {"files": [{"name": "book.pdf", "source": "original", "size": "3"}]},
    )

    def fake_download(url: str, destination: Path, **kwargs: object) -> DownloadResult:
        destination.write_bytes(b"pdf")
        return DownloadResult(3, "checksum", None, None)

    monkeypatch.setattr("sanskrit_corpus.ia_ocr.download_file", fake_download)
    result = pull_and_ocr_internet_archive(tmp_path, shard_count=2, shard_index=1, backend=FakeBackend())
    output = tmp_path / "data/raw/internet_archive/one/_paddleocr_v5_sa.txt.gz"

    assert result.item_count == result.ocr_count == 1
    assert gzip.open(output, "rt", encoding="utf-8").read() == "संस्कृतम्"
    assert not list(tmp_path.rglob("source.pdf"))


def test_invalid_shard_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        pull_and_ocr_internet_archive(tmp_path, shard_count=2, shard_index=2, backend=FakeBackend())


def test_paddle_backend_collects_page_text_and_scores(tmp_path: Path) -> None:
    class Result:
        json = {"res": {"rec_texts": ["प्रथमः", "द्वितीयः"], "rec_scores": [0.8, 0.9]}}

    class Pipeline:
        def predict(self, path: str) -> list[Result]:
            return [Result()]

    backend = PaddleDevanagariBackend.__new__(PaddleDevanagariBackend)
    backend._pipeline = Pipeline()  # type: ignore[assignment]

    text, scores = backend.recognize_pdf(tmp_path / "book.pdf")

    assert "<<<PAGE 1>>>\nप्रथमः\nद्वितीयः" in text
    assert scores == [0.8, 0.9]


@pytest.mark.parametrize(
    ("files", "missing_only"),
    [
        ([], False),
        ([{"name": "book_djvu.txt"}, {"name": "book.pdf", "source": "original"}], True),
    ],
)
def test_pull_and_ocr_skips_unusable_items(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    files: list[dict[str, str]],
    missing_only: bool,
) -> None:
    monkeypatch.setattr("sanskrit_corpus.ia_ocr.search_items", lambda query, limit: [{"identifier": "item"}])
    monkeypatch.setattr("sanskrit_corpus.ia_ocr.item_metadata", lambda identifier: {"files": files})

    result = pull_and_ocr_internet_archive(tmp_path, missing_ocr_only=missing_only, backend=FakeBackend())

    assert result.skipped_count == 1
    assert result.ocr_count == result.failed_count == 0


def test_pull_and_ocr_records_failure_and_resumes_existing_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sanskrit_corpus.ia_ocr.search_items",
        lambda query, limit: [{"identifier": "bad"}, {"identifier": "done"}],
    )
    monkeypatch.setattr(
        "sanskrit_corpus.ia_ocr.item_metadata",
        lambda identifier: {"files": [{"name": "book.pdf", "source": "original", "size": "3"}]},
    )
    done = tmp_path / "data/raw/internet_archive/done"
    done.mkdir(parents=True)
    (done / "_paddleocr_v5_sa.txt.gz").write_bytes(b"existing")
    monkeypatch.setattr("sanskrit_corpus.ia_ocr.download_file", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("network")))

    result = pull_and_ocr_internet_archive(tmp_path, backend=FakeBackend())
    rows = [json.loads(line) for line in Path(result.manifest_path).read_text(encoding="utf-8").splitlines()]

    assert result.failed_count == result.skipped_count == 1
    assert rows[0]["status"].startswith("failed:OSError:network")
