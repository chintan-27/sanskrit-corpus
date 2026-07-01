import json
from pathlib import Path

from sanskrit_corpus.processing import normalize_text, process_sources, transliterate_iast_to_devanagari


def test_normalize_text() -> None:
    assert normalize_text("  श्री\uFEFF  रामः\n") == "श्री रामः"


def test_transliterate_iast_to_devanagari_handles_vedic_lateral() -> None:
    assert transliterate_iast_to_devanagari("agnim īḷe") == "अग्निम् ईळे"


def test_process_itihasa_fixture(tmp_path: Path) -> None:
    raw = tmp_path / "data" / "raw" / "itihasa"
    raw.mkdir(parents=True)
    (raw / "train.sn.csv").write_text("धर्मः\n", encoding="utf-8")
    (raw / "train.en.csv").write_text("Dharma\n", encoding="utf-8")

    result = process_sources(tmp_path, "itihasa", force=True)[0]
    row = json.loads((tmp_path / "data" / "processed" / "itihasa.jsonl").read_text(encoding="utf-8"))

    assert result.record_count == 1
    assert row["record_type"] == "parallel_sentence"
    assert row["text"] == "धर्मः"
    assert row["translation"] == "Dharma"


def test_process_limit(tmp_path: Path) -> None:
    raw = tmp_path / "data" / "raw" / "itihasa"
    raw.mkdir(parents=True)
    (raw / "train.sn.csv").write_text("एकम्\nद्वे\n", encoding="utf-8")
    (raw / "train.en.csv").write_text("One\nTwo\n", encoding="utf-8")

    result = process_sources(tmp_path, "itihasa", force=True, limit=1)[0]

    assert result.record_count == 1
    assert len((tmp_path / "data" / "processed" / "itihasa.jsonl").read_text(encoding="utf-8").splitlines()) == 1


def test_process_ud_fixture(tmp_path: Path) -> None:
    raw = tmp_path / "data" / "raw" / "ud_sanskrit_vedic"
    raw.mkdir(parents=True)
    (raw / "sa_vedic-ud-train.conllu").write_text(
        "# text = agnim īḷe\n# sent_id = rv-1\n1\tagnim\tagni\tNOUN\t_\t_\t0\troot\t_\t_\n\n",
        encoding="utf-8",
    )

    result = process_sources(tmp_path, "ud_sanskrit_vedic", force=True)[0]
    row = json.loads((tmp_path / "data" / "processed" / "ud_sanskrit_vedic.jsonl").read_text(encoding="utf-8"))

    assert result.record_count == 1
    assert row["sent_id"] == "rv-1"
    assert row["text"] == "अग्निम् ईळे"
    assert row["text_lang"] == "sa-Deva"
    assert row["text_latn"] == "agnim īḷe"


def test_process_naamah_fixture(tmp_path: Path) -> None:
    raw = tmp_path / "data" / "raw" / "naamah"
    raw.mkdir(parents=True)
    (raw / "Sanskrit_NER_Silver_v1.jsonl").write_text(
        '{"tokens":["रामः","गच्छति"],"ner_tags":[1,0]}\n',
        encoding="utf-8",
    )

    result = process_sources(tmp_path, "naamah", force=True)[0]
    row = json.loads((tmp_path / "data" / "processed" / "naamah.jsonl").read_text(encoding="utf-8"))

    assert result.record_count == 1
    assert row["record_type"] == "ner_sentence"
    assert row["tokens"] == ["रामः", "गच्छति"]


def test_process_gretil_tei_fixture(tmp_path: Path) -> None:
    raw = tmp_path / "data" / "raw" / "gretil_sanskrit" / "extracted" / "1_sanskr" / "tei"
    raw.mkdir(parents=True)
    (raw / "sa_test.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader><fileDesc><titleStmt><title>Test Text</title></titleStmt></fileDesc></teiHeader>
  <text><body><head>English Header</head><p>agnim īḷe purohitaṃ</p><note>agnim īḷe duplicate</note></body></text>
</TEI>
""",
        encoding="utf-8",
    )

    result = process_sources(tmp_path, "gretil_sanskrit", force=True)[0]
    row = json.loads((tmp_path / "data" / "processed" / "gretil_sanskrit.jsonl").read_text(encoding="utf-8"))

    assert result.record_count == 1
    assert row["release_status"] == "needs_audit"
    assert row["title"] == "Test Text"
    assert row["text"] == "अग्निम् ईळे पुरोहितं"
    assert row["text_latn"] == "agnim īḷe purohitaṃ"
    assert "English Header" not in row["text_latn"]
    assert "duplicate" not in row["text_latn"]


def test_process_saamayik_fixture(tmp_path: Path) -> None:
    raw = tmp_path / "data" / "raw" / "saamayik" / "data" / "final_data"
    raw.mkdir(parents=True)
    (raw / "train.sa").write_text("गुरुः पठति\n", encoding="utf-8")
    (raw / "train.en").write_text("The teacher reads\n", encoding="utf-8")

    result = process_sources(tmp_path, "saamayik", force=True)[0]
    row = json.loads((tmp_path / "data" / "processed" / "saamayik.jsonl").read_text(encoding="utf-8"))

    assert result.record_count == 1
    assert row["release_status"] == "needs_audit"
    assert row["text_lang"] == "sa-Deva"
    assert row["translation"] == "The teacher reads"
