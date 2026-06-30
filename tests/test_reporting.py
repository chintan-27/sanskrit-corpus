import json
from pathlib import Path

from sanskrit_corpus.reporting import write_report


def test_write_report(tmp_path: Path) -> None:
    raw = tmp_path / "data" / "raw" / "example"
    raw.mkdir(parents=True)
    (raw / "a.txt").write_text("raw", encoding="utf-8")
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    (processed / "example.jsonl").write_text('{"x":1}\n{"x":2}\n', encoding="utf-8")

    path = write_report(tmp_path)
    report = json.loads(path.read_text(encoding="utf-8"))

    assert report["raw_sources"][0]["source_id"] == "example"
    assert report["processed_outputs"][0]["record_count"] == 2
