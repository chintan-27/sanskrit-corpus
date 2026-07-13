import io
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from sanskrit_corpus.manifest import SourceRecord
from sanskrit_corpus.sources import (
    DownloadResult,
    GitSource,
    HuggingFaceDatasetSource,
    PullContext,
    UnavailableSource,
    UrlFileSource,
    ZipArchiveSource,
    _safe_extract,
    build_sources,
    download_file,
    fetch_bytes,
    fetch_json,
)


def _source_record(source_id: str = "fixture") -> SourceRecord:
    return SourceRecord(source_id, "Fixture", "https://example.test", "test", "test", "needs_audit", "needs_audit", "fixture")


def test_unclear_sources_are_not_releasable() -> None:
    sources = build_sources()

    assert sources["kaggle_sanskrit_text_corpus"].record.release_status == "needs_audit"
    assert sources["aikosh_sanskrit_post_ocr"].record.release_status == "needs_audit"
    assert sources["github_oliverhellwig"].record.release_status == "releasable"
    assert sources["gretil_sanskrit"].record.release_status == "restricted"
    assert sources["sarit_corpus"].record.release_status == "needs_audit"
    assert sources["saamayik"].record.release_status == "needs_audit"
    assert sources["sanskrit_wikisource"].record.release_status == "needs_audit"
    assert sources["gyaandweep_shabdkosha"].record.release_status == "needs_audit"
    assert sources["learnsanskrit_grammar"].record.release_status == "restricted"


def test_synthetic_source_is_quarantined() -> None:
    source = build_sources()["samhitika_0_0_1"].record

    assert source.release_status == "synthetic"
    assert source.release_status != "releasable"


def test_safe_extract_rejects_path_traversal(tmp_path: Path) -> None:
    archive_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../outside.txt", "bad")

    with zipfile.ZipFile(archive_path) as archive, pytest.raises(RuntimeError, match="unsafe archive member"):
        _safe_extract(archive, tmp_path / "output")


def test_download_quota_preserves_existing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    destination = tmp_path / "payload.bin"
    destination.write_bytes(b"previous")

    class Response(io.BytesIO):
        headers = {"ETag": "test", "Last-Modified": "today"}

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: Response(b"too large"))

    with pytest.raises(RuntimeError, match="exceeds"):
        download_file("https://example.test/file", destination, max_bytes=3)

    assert destination.read_bytes() == b"previous"


def test_fetch_helpers_enforce_response_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: Response(b'{"ok": true}'))
    assert fetch_json("https://example.test") == {"ok": True}
    with pytest.raises(RuntimeError, match="exceeds"):
        fetch_bytes("https://example.test", max_bytes=2)


def test_url_source_publishes_atomically(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = UrlFileSource(_source_record(), "https://example.test/file", "file.txt")

    def fake_download(url: str, destination: Path, **kwargs) -> DownloadResult:
        destination.write_text("payload", encoding="utf-8")
        return DownloadResult(7, "checksum", "etag", "today")

    monkeypatch.setattr("sanskrit_corpus.sources.download_file", fake_download)
    result = source.pull(PullContext(tmp_path, sample=False, dry_run=False, force=False))
    cached = source.pull(PullContext(tmp_path, sample=False, dry_run=False, force=False))

    assert result.status == "ok"
    assert result.etag == "etag"
    assert cached.status == "ok"
    assert (tmp_path / "data" / "raw" / "fixture" / "file.txt").read_text(encoding="utf-8") == "payload"


def test_zip_source_extracts_safe_archive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = ZipArchiveSource(_source_record(), "https://example.test/archive", "archive.zip")

    def fake_download(url: str, destination: Path, **kwargs) -> DownloadResult:
        with zipfile.ZipFile(destination, "w") as archive:
            archive.writestr("nested/file.txt", "payload")
        return DownloadResult(destination.stat().st_size, "checksum", None, None)

    monkeypatch.setattr("sanskrit_corpus.sources.download_file", fake_download)
    result = source.pull(PullContext(tmp_path, sample=True, dry_run=False, force=False))

    assert result.status == "ok"
    assert (tmp_path / "data" / "raw" / "fixture" / "extracted" / "nested" / "file.txt").exists()


def test_huggingface_source_selects_and_downloads_sample(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = HuggingFaceDatasetSource(_source_record(), "org/repo", sample_file_limit=2)
    monkeypatch.setattr(source, "_repo_tree", lambda: [{"type": "file", "path": "README.md"}, {"type": "file", "path": "data.csv"}])

    def fake_download(remote: str, local: Path) -> None:
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text(remote, encoding="utf-8")

    monkeypatch.setattr(source, "_download_file", fake_download)

    result = source.pull(PullContext(tmp_path, sample=True, dry_run=False, force=False))

    assert result.status == "ok"
    assert source._select_files(["README.md", "data.csv", "ignored.bin"], sample=False) == ["README.md", "data.csv"]


def test_git_and_unavailable_sources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = GitSource(_source_record("git_fixture"), "https://example.test/repo.git")

    def fake_run(command, **kwargs):
        if "clone" in command:
            Path(command[-1], "payload.txt").write_text("payload", encoding="utf-8")
            return SimpleNamespace(stdout="")
        return SimpleNamespace(stdout="abc123\n")

    monkeypatch.setattr("sanskrit_corpus.sources.subprocess.run", fake_run)
    result = source.pull(PullContext(tmp_path, sample=True, dry_run=False, force=False))
    unavailable = UnavailableSource(_source_record("manual")).pull(PullContext(tmp_path, True, False, False))

    assert result.source_revision == "abc123"
    assert unavailable.status == "failed"
