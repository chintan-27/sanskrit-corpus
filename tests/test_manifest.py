from pathlib import Path

from sanskrit_corpus.manifest import SourceRecord, directory_stats, write_source_registry


def test_write_source_registry_jsonl(tmp_path: Path) -> None:
    path = write_source_registry(
        tmp_path,
        [
            SourceRecord(
                "example",
                "Example",
                "https://example.test",
                "web",
                "manual",
                "needs_audit",
                "needs_audit",
                "audit before release",
            )
        ],
    )

    text = path.read_text(encoding="utf-8")
    assert '"source_id": "example"' in text
    assert '"release_status": "needs_audit"' in text


def test_directory_stats_are_stable(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / "b.txt").write_text("beta", encoding="utf-8")
    (data / "a.txt").write_text("alpha", encoding="utf-8")

    first = directory_stats(data)
    second = directory_stats(data)

    assert first == second
    assert first[0] == 2
    assert first[1] == len("alpha") + len("beta")
