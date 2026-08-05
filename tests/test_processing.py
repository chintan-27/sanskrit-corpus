import bz2
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from sanskrit_corpus.processing import clean_html_text, clean_wikitext, normalize_text, process_sources, transliterate_iast_to_devanagari


def test_normalize_text() -> None:
    assert normalize_text("  श्री\uFEFF  रामः\n") == "श्री रामः"


def test_process_sangraha_verified_sanskrit_fixture(tmp_path: Path) -> None:
    raw = tmp_path / "data" / "raw" / "sangraha_verified_sanskrit" / "verified" / "san"
    raw.mkdir(parents=True)
    pq.write_table(
        pa.table(
            {
                "doc_id": ["doc-1", "doc-2"],
                "type": ["website", "ocr"],
                "text": ["  रामः   वनं गच्छति। ", ""],
            }
        ),
        raw / "part-000.parquet",
    )

    result = process_sources(tmp_path, "sangraha_verified_sanskrit", force=True)[0]
    row = json.loads((tmp_path / "data" / "processed" / "sangraha_verified_sanskrit.jsonl").read_text(encoding="utf-8"))

    assert result.record_count == 1
    assert row["text"] == "रामः वनं गच्छति।"
    assert row["source_document_id"] == "doc-1"
    assert row["source_material_type"] == "website"
    assert row["corpus_partition"] == "verified/san"
    assert row["provenance_class"] == "human_source_verified"
    assert row["release_status"] == "needs_audit"


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


def test_process_itihasa_preserves_unquoted_commas(tmp_path: Path) -> None:
    raw = tmp_path / "data" / "raw" / "itihasa"
    raw.mkdir(parents=True)
    (raw / "train.sn.csv").write_text("रामः, सीता च वनं गतौ।\n", encoding="utf-8")
    (raw / "train.en.csv").write_text("Rama, and Sita went to the forest.\n", encoding="utf-8")

    result = process_sources(tmp_path, "itihasa", force=True)[0]
    row = json.loads((tmp_path / "data" / "processed" / "itihasa.jsonl").read_text(encoding="utf-8"))

    assert result.record_count == 1
    assert row["text"] == "रामः, सीता च वनं गतौ।"
    assert row["translation"] == "Rama, and Sita went to the forest."


def test_process_ud_fixture(tmp_path: Path) -> None:
    raw = tmp_path / "data" / "raw" / "ud_sanskrit_vedic"
    raw.mkdir(parents=True)
    (raw / "sa_vedic-ud-train.conllu").write_text(
        "# text = agnim īḷe\n# sent_id = rv-1\n"
        "1\tagnim\tagni\tNOUN\t_\tCase=Acc|Number=Sing\t0\troot\t_\t_\n"
        "2\tīḷe\tīḍ\tVERB\t_\tMood=Ind|Person=1\t1\tconj\t_\t_\n\n",
        encoding="utf-8",
    )

    result = process_sources(tmp_path, "ud_sanskrit_vedic", force=True)[0]
    row = json.loads((tmp_path / "data" / "processed" / "ud_sanskrit_vedic.jsonl").read_text(encoding="utf-8"))

    assert result.record_count == 1
    assert row["sent_id"] == "rv-1"
    assert row["text"] == "अग्निम् ईळे"
    assert row["text_lang"] == "sa-Deva"
    assert row["text_latn"] == "agnim īḷe"
    assert row["tokens"][0]["form"] == "अग्निम्"
    assert row["tokens"][0]["lemma"] == "अग्नि"
    assert row["tokens"][0]["feats"] == {"Case": "Acc", "Number": "Sing"}
    assert row["tokens"][1]["deprel"] == "conj"


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
    assert row["release_status"] == "restricted"
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


def test_clean_wikitext() -> None:
    assert clean_wikitext("'''रामः''' [[अयोध्या|अयोध्यायाम्]] {{x|y}} <ref>note</ref>") == "रामः अयोध्यायाम्"


def test_process_mediawiki_fixture(tmp_path: Path) -> None:
    raw = tmp_path / "data" / "raw" / "sanskrit_wikipedia"
    raw.mkdir(parents=True)
    xml = """<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/">
  <page><title>रामः</title><ns>0</ns><id>1</id><revision><text>
  रामः अयोध्यायाः राजकुमारः आसीत्। रामायणग्रन्थे तस्य कथा विस्तरेण वर्णिता अस्ति।
  </text></revision></page>
  <page><title>Talk</title><ns>1</ns><id>2</id><revision><text>skip this page</text></revision></page>
</mediawiki>"""
    with bz2.open(raw / "sawiki-latest-pages-articles.xml.bz2", "wt", encoding="utf-8") as handle:
        handle.write(xml)

    result = process_sources(tmp_path, "sanskrit_wikipedia", force=True)[0]
    row = json.loads((tmp_path / "data" / "processed" / "sanskrit_wikipedia.jsonl").read_text(encoding="utf-8"))

    assert result.record_count == 1
    assert row["release_status"] == "releasable"
    assert row["title"] == "रामः"


def test_process_github_oliverhellwig_fixture(tmp_path: Path) -> None:
    raw = tmp_path / "data" / "raw" / "github_oliverhellwig" / "dcs" / "data" / "conllu" / "files" / "Work"
    raw.mkdir(parents=True)
    (raw / "sample.conllu").write_text(
        "## text: Test Work\n## chapter: 1\n# text = agnim īḷe purohitaṃ\n# sent_id = 10\n"
        "1\tagnim\tagni\tNOUN\t_\tCase=Acc|Number=Sing\t0\troot\t_\t"
        "LemmaId=1|Unsandhied=agniṃ\n\n",
        encoding="utf-8",
    )

    result = process_sources(tmp_path, "github_oliverhellwig", force=True)[0]
    row = json.loads((tmp_path / "data" / "processed" / "github_oliverhellwig.jsonl").read_text(encoding="utf-8"))

    assert result.record_count == 1
    assert row["release_status"] == "releasable"
    assert row["title"] == "Test Work"
    assert row["chapter"] == "1"
    assert row["text"] == "अग्निम् ईळे पुरोहितं"
    assert row["sentence_number"] == 1
    assert row["record_id"].endswith(":1:10")
    assert row["tokens"][0]["lemma"] == "अग्नि"
    assert row["tokens"][0]["misc"]["LemmaId"] == "1"
    assert row["tokens"][0]["unsandhied"] == "अग्निं"


def test_process_single_html_fixture(tmp_path: Path) -> None:
    raw = tmp_path / "data" / "raw" / "learnsanskrit_grammar"
    raw.mkdir(parents=True)
    (raw / "grammar.html").write_text(
        "<html><body><nav>Search</nav><h1>Sanskrit Grammar</h1><p>Cases and sandhi are important.</p></body></html>",
        encoding="utf-8",
    )

    result = process_sources(tmp_path, "learnsanskrit_grammar", force=True)[0]
    row = json.loads((tmp_path / "data" / "processed" / "learnsanskrit_grammar.jsonl").read_text(encoding="utf-8"))

    assert result.record_count == 1
    assert row["release_status"] == "restricted"
    assert "Sanskrit Grammar" in row["text"]


def test_clean_html_text_removes_scripts() -> None:
    assert clean_html_text("<script>bad()</script><p>रामः पठति</p>") == "रामः पठति"


def test_process_internet_archive_fixture(tmp_path: Path) -> None:
    raw = tmp_path / "data" / "raw" / "internet_archive" / "item1"
    raw.mkdir(parents=True)
    (raw / "item1_djvu.txt").write_text("रामः " * 30, encoding="utf-8")

    result = process_sources(tmp_path, "internet_archive", force=True)[0]
    row = json.loads((tmp_path / "data" / "processed" / "internet_archive.jsonl").read_text(encoding="utf-8"))

    assert result.record_count == 1
    assert row["release_status"] == "needs_audit"
    assert row["source_url"] == "https://archive.org/details/item1"


def test_parallel_mismatch_preserves_existing_output(tmp_path: Path) -> None:
    raw = tmp_path / "data" / "raw" / "itihasa"
    raw.mkdir(parents=True)
    (raw / "train.sn.csv").write_text("एकम्\nद्वे\n", encoding="utf-8")
    (raw / "train.en.csv").write_text("One\n", encoding="utf-8")
    output = tmp_path / "data" / "processed" / "itihasa.jsonl"
    output.parent.mkdir(parents=True)
    output.write_text("previous output\n", encoding="utf-8")

    result = process_sources(tmp_path, "itihasa", force=True)[0]

    assert result.status == "failed"
    assert output.read_text(encoding="utf-8") == "previous output\n"
