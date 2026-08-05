import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from sanskrit_corpus.grammar import build_grammar_verified


def _record(source_id: str, record_id: str, text: str, split: str | None = None) -> dict:
    row = {
        "record_id": record_id,
        "source_id": source_id,
        "text": text,
        "text_latn": "agnim",
        "source_path": "work/chapter.conllu",
        "title": "Work",
        "tokens": [
            {
                "form": "अग्निम्",
                "form_latn": "agnim",
                "lemma": "अग्नि",
                "lemma_latn": "agni",
                "unsandhied": "अग्निम्",
                "unsandhied_latn": "agnim",
                "upos": "NOUN",
                "xpos": "_",
                "feats": {"Case": "Acc"},
                "head": "0",
                "deprel": "root",
            }
        ],
    }
    if split:
        row["split"] = split
    return row


def test_build_grammar_verified_preserves_ud_priority_and_views(tmp_path: Path) -> None:
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    ud = _record("ud_sanskrit_vedic", "ud:1", "अग्निम्", "dev")
    dcs_duplicate = _record("github_oliverhellwig", "dcs:1", "अग्निम्")
    dcs_unique = _record("github_oliverhellwig", "dcs:2", "वायुम्")
    (processed / "ud_sanskrit_vedic.jsonl").write_text(json.dumps(ud, ensure_ascii=False) + "\n", encoding="utf-8")
    (processed / "github_oliverhellwig.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in (dcs_duplicate, dcs_unique)) + "\n",
        encoding="utf-8",
    )

    manifest_path = build_grammar_verified(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = pq.read_table(tmp_path / "data" / "grammar" / "grammar_verified.parquet").to_pylist()

    assert manifest["counts"]["records"] == 2
    assert manifest["counts"]["duplicates_excluded"] == 1
    assert rows[0]["split"] == "dev"
    assert rows[0]["lemma_sequence"] == ["अग्नि"]
    assert rows[0]["morph_sequence"] == ["अग्नि<NOUN|Case=Acc>"]
    assert rows[0]["tokens"][0]["feats"] == [("Case", "Acc")]
    with pytest.raises(FileExistsError):
        build_grammar_verified(tmp_path)


def test_build_grammar_verified_requires_both_sources(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        build_grammar_verified(tmp_path)
