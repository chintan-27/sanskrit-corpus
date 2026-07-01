from __future__ import annotations

import bz2
import csv
import json
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import dataclass
from html import unescape
from pathlib import Path

from indic_transliteration import sanscript

from .manifest import append_jsonl
from .sources import build_sources


csv.field_size_limit(sys.maxsize)


@dataclass(frozen=True)
class ProcessResult:
    source_id: str
    status: str
    output_path: str
    record_count: int
    error: str | None = None


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text)
    return " ".join(normalized.replace("\ufeff", "").split())


def transliterate_iast_to_devanagari(text: str) -> str:
    # UD Vedic uses ḷ for the retroflex lateral in forms like īḷe; sanscript expects ḻ.
    vedic_lateral_normalized = text.replace("ḷ", "ḻ").replace("Ḷ", "Ḻ")
    return normalize_text(sanscript.transliterate(vedic_lateral_normalized, sanscript.IAST, sanscript.DEVANAGARI))


def process_sources(root: Path, source_id: str = "all", force: bool = False, limit: int | None = None) -> list[ProcessResult]:
    processors = {
        "itihasa": process_itihasa,
        "ud_sanskrit_vedic": process_ud_sanskrit_vedic,
        "naamah": process_naamah,
        "samhitika_0_0_1": process_samhitika,
        "gretil_sanskrit": process_gretil_sanskrit,
        "sarit_corpus": process_sarit_corpus,
        "saamayik": process_saamayik,
        "sanskrit_wikipedia": process_sanskrit_wikipedia,
        "sanskrit_wikisource": process_sanskrit_wikisource,
        "github_oliverhellwig": process_github_oliverhellwig,
        "gyaandweep_shabdkosha": process_gyaandweep_shabdkosha,
        "learnsanskrit_grammar": process_learnsanskrit_grammar,
    }
    selected = list(processors) if source_id == "all" else [source_id]
    results: list[ProcessResult] = []
    for selected_id in selected:
        processor = processors.get(selected_id)
        if processor is None:
            results.append(ProcessResult(selected_id, "skipped", "", 0, "no processor is available for this source"))
            continue
        try:
            results.append(processor(root, force=force, limit=limit))
        except Exception as exc:
            results.append(ProcessResult(selected_id, "failed", "", 0, str(exc)))
    return results


def _output_path(root: Path, source_id: str, force: bool) -> Path:
    output = root / "data" / "processed" / f"{source_id}.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not force:
        raise FileExistsError(f"{output} already exists; pass --force to replace it")
    output.write_text("", encoding="utf-8")
    return output


def _source_metadata(source_id: str) -> dict[str, str]:
    record = build_sources()[source_id].record
    return {
        "license_label": record.license_label,
        "release_status": record.release_status,
        "source_url": record.url,
    }


def process_itihasa(root: Path, force: bool = False, limit: int | None = None) -> ProcessResult:
    source_id = "itihasa"
    raw_dir = root / "data" / "raw" / source_id
    output = _output_path(root, source_id, force)
    metadata = _source_metadata(source_id)
    count = 0

    for split in ("train", "dev", "test"):
        sn_path = raw_dir / f"{split}.sn.csv"
        en_path = raw_dir / f"{split}.en.csv"
        if not sn_path.exists() or not en_path.exists():
            continue
        rows = []
        with sn_path.open(encoding="utf-8", newline="") as sn_file, en_path.open(encoding="utf-8", newline="") as en_file:
            for line_number, (sn_row, en_row) in enumerate(zip(csv.reader(sn_file), csv.reader(en_file)), start=1):
                sanskrit = normalize_text(sn_row[0]) if sn_row else ""
                english = normalize_text(en_row[0]) if en_row else ""
                if not sanskrit:
                    continue
                count += 1
                rows.append(
                    {
                        "record_id": f"{source_id}:{split}:{line_number}",
                        "source_id": source_id,
                        "record_type": "parallel_sentence",
                        "split": split,
                        "text": sanskrit,
                        "text_lang": "sa",
                        "translation": english,
                        "translation_lang": "en",
                        "source_path": f"{split}.sn.csv",
                        "line_number": line_number,
                        "normalization": ["unicode_nfc", "whitespace_squeeze"],
                        **metadata,
                    }
                )
                if limit is not None and count >= limit:
                    append_jsonl(output, rows)
                    return ProcessResult(source_id, "ok", str(output), count)
        append_jsonl(output, rows)

    return ProcessResult(source_id, "ok", str(output), count)


def process_ud_sanskrit_vedic(root: Path, force: bool = False, limit: int | None = None) -> ProcessResult:
    source_id = "ud_sanskrit_vedic"
    raw_dir = root / "data" / "raw" / source_id
    output = _output_path(root, source_id, force)
    metadata = _source_metadata(source_id)
    count = 0

    for split in ("train", "dev", "test"):
        path = raw_dir / f"sa_vedic-ud-{split}.conllu"
        if not path.exists():
            continue
        rows = []
        for sentence in _read_conllu_sentences(path):
            text_latn = normalize_text(sentence.get("text", ""))
            if not text_latn:
                continue
            text = transliterate_iast_to_devanagari(text_latn)
            count += 1
            sent_id = sentence.get("sent_id", str(count))
            rows.append(
                {
                    "record_id": f"{source_id}:{split}:{sent_id}",
                    "source_id": source_id,
                    "record_type": "treebank_sentence",
                    "split": split,
                    "text": text,
                    "text_lang": "sa-Deva",
                    "text_latn": text_latn,
                    "text_latn_scheme": "IAST",
                    "sent_id": sent_id,
                    "citation_text": sentence.get("citation_text"),
                    "citation_chapter": sentence.get("citation_chapter"),
                    "source_path": path.name,
                    "normalization": ["unicode_nfc", "whitespace_squeeze", "iast_to_devanagari"],
                    **metadata,
                }
            )
            if limit is not None and count >= limit:
                append_jsonl(output, rows)
                return ProcessResult(source_id, "ok", str(output), count)
        append_jsonl(output, rows)

    return ProcessResult(source_id, "ok", str(output), count)


def _read_conllu_sentences(path: Path) -> Iterable[dict[str, str]]:
    current: dict[str, str] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line:
                if current:
                    yield current
                    current = {}
                continue
            if line.startswith("# ") and " = " in line:
                key, value = line[2:].split(" = ", 1)
                current[key] = value
        if current:
            yield current


def process_naamah(root: Path, force: bool = False, limit: int | None = None) -> ProcessResult:
    source_id = "naamah"
    raw_path = root / "data" / "raw" / source_id / "Sanskrit_NER_Silver_v1.jsonl"
    output = _output_path(root, source_id, force)
    metadata = _source_metadata(source_id)
    count = 0
    rows = []

    with raw_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            payload = json.loads(line)
            tokens = payload.get("tokens") or []
            text = normalize_text(" ".join(tokens))
            if not text:
                continue
            count += 1
            rows.append(
                {
                    "record_id": f"{source_id}:{line_number}",
                    "source_id": source_id,
                    "record_type": "ner_sentence",
                    "text": text,
                    "text_lang": "sa-Deva",
                    "tokens": tokens,
                    "ner_tags": payload.get("ner_tags"),
                    "source_path": raw_path.name,
                    "line_number": line_number,
                    "normalization": ["unicode_nfc", "whitespace_squeeze"],
                    **metadata,
                }
            )
            if len(rows) >= 5000:
                append_jsonl(output, rows)
                rows = []
            if limit is not None and count >= limit:
                append_jsonl(output, rows)
                return ProcessResult(source_id, "ok", str(output), count)
    append_jsonl(output, rows)

    return ProcessResult(source_id, "ok", str(output), count)


def process_samhitika(root: Path, force: bool = False, limit: int | None = None) -> ProcessResult:
    import pyarrow.parquet as pq

    source_id = "samhitika_0_0_1"
    raw_path = root / "data" / "raw" / source_id / "translations.parquet"
    output = _output_path(root, source_id, force)
    metadata = _source_metadata(source_id)
    count = 0
    rows = []

    parquet = pq.ParquetFile(raw_path)
    for batch in parquet.iter_batches(columns=["bookcorpus_id", "text"], batch_size=5000):
        payload = batch.to_pydict()
        for bookcorpus_id, text_value in zip(payload["bookcorpus_id"], payload["text"]):
            text = normalize_text(text_value or "")
            if not text:
                continue
            count += 1
            rows.append(
                {
                    "record_id": f"{source_id}:{bookcorpus_id if bookcorpus_id is not None else count}",
                    "source_id": source_id,
                    "record_type": "synthetic_translation",
                    "text": text,
                    "text_lang": "sa",
                    "bookcorpus_id": bookcorpus_id,
                    "source_path": raw_path.name,
                    "normalization": ["unicode_nfc", "whitespace_squeeze"],
                    **metadata,
                }
            )
            if len(rows) >= 5000:
                append_jsonl(output, rows)
                rows = []
            if limit is not None and count >= limit:
                append_jsonl(output, rows)
                return ProcessResult(source_id, "ok", str(output), count)
    append_jsonl(output, rows)

    return ProcessResult(source_id, "ok", str(output), count)


def process_gretil_sanskrit(root: Path, force: bool = False, limit: int | None = None) -> ProcessResult:
    source_id = "gretil_sanskrit"
    raw_dir = root / "data" / "raw" / source_id / "extracted" / "1_sanskr" / "tei"
    output = _output_path(root, source_id, force)
    metadata = _source_metadata(source_id)
    count = 0
    rows = []

    for xml_path in sorted(raw_dir.glob("*.xml")):
        record = _read_gretil_tei(xml_path)
        if record is None:
            continue
        count += 1
        text_latn = normalize_text(record["text_latn"])
        rows.append(
            {
                "record_id": f"{source_id}:{xml_path.stem}",
                "source_id": source_id,
                "record_type": "tei_document",
                "title": record.get("title"),
                "text": transliterate_iast_to_devanagari(text_latn),
                "text_lang": "sa-Deva",
                "text_latn": text_latn,
                "text_latn_scheme": "IAST",
                "source_path": str(xml_path.relative_to(root / "data" / "raw" / source_id)),
                "normalization": ["unicode_nfc", "whitespace_squeeze", "tei_body_itertext", "iast_to_devanagari"],
                **metadata,
            }
        )
        if len(rows) >= 100:
            append_jsonl(output, rows)
            rows = []
        if limit is not None and count >= limit:
            append_jsonl(output, rows)
            return ProcessResult(source_id, "ok", str(output), count)
    append_jsonl(output, rows)

    return ProcessResult(source_id, "ok", str(output), count)


def process_sarit_corpus(root: Path, force: bool = False, limit: int | None = None) -> ProcessResult:
    source_id = "sarit_corpus"
    raw_dir = root / "data" / "raw" / source_id
    output = _output_path(root, source_id, force)
    metadata = _source_metadata(source_id)
    count = 0
    rows = []

    for xml_path in sorted(raw_dir.glob("*.xml")):
        if xml_path.name.startswith("00-") or xml_path.name == "saritcorpus.xml":
            continue
        record = _read_gretil_tei(xml_path)
        if record is None:
            continue
        count += 1
        text_latn = normalize_text(record["text_latn"])
        rows.append(
            {
                "record_id": f"{source_id}:{xml_path.stem}",
                "source_id": source_id,
                "record_type": "tei_document",
                "title": record.get("title"),
                "text": transliterate_iast_to_devanagari(text_latn),
                "text_lang": "sa-Deva",
                "text_latn": text_latn,
                "text_latn_scheme": "IAST",
                "source_path": xml_path.name,
                "normalization": ["unicode_nfc", "whitespace_squeeze", "tei_body_itertext", "iast_to_devanagari"],
                **metadata,
            }
        )
        if len(rows) >= 25:
            append_jsonl(output, rows)
            rows = []
        if limit is not None and count >= limit:
            append_jsonl(output, rows)
            return ProcessResult(source_id, "ok", str(output), count)
    append_jsonl(output, rows)

    return ProcessResult(source_id, "ok", str(output), count)


def process_saamayik(root: Path, force: bool = False, limit: int | None = None) -> ProcessResult:
    source_id = "saamayik"
    raw_dir = root / "data" / "raw" / source_id / "data" / "final_data"
    output = _output_path(root, source_id, force)
    metadata = _source_metadata(source_id)
    count = 0

    for split in ("train", "dev", "test"):
        sa_path = raw_dir / f"{split}.sa"
        en_path = raw_dir / f"{split}.en"
        if not sa_path.exists() or not en_path.exists():
            continue
        rows = []
        with sa_path.open(encoding="utf-8") as sa_file, en_path.open(encoding="utf-8") as en_file:
            for line_number, (sa_line, en_line) in enumerate(zip(sa_file, en_file), start=1):
                sanskrit = normalize_text(sa_line)
                english = normalize_text(en_line)
                if not sanskrit:
                    continue
                count += 1
                rows.append(
                    {
                        "record_id": f"{source_id}:{split}:{line_number}",
                        "source_id": source_id,
                        "record_type": "parallel_sentence",
                        "split": split,
                        "text": sanskrit,
                        "text_lang": "sa-Deva",
                        "translation": english,
                        "translation_lang": "en",
                        "source_path": f"data/final_data/{split}.sa",
                        "line_number": line_number,
                        "normalization": ["unicode_nfc", "whitespace_squeeze"],
                        **metadata,
                    }
                )
                if limit is not None and count >= limit:
                    append_jsonl(output, rows)
                    return ProcessResult(source_id, "ok", str(output), count)
        append_jsonl(output, rows)

    return ProcessResult(source_id, "ok", str(output), count)


def process_sanskrit_wikipedia(root: Path, force: bool = False, limit: int | None = None) -> ProcessResult:
    return _process_mediawiki_dump(root, "sanskrit_wikipedia", "sawiki-latest-pages-articles.xml.bz2", force, limit)


def process_sanskrit_wikisource(root: Path, force: bool = False, limit: int | None = None) -> ProcessResult:
    return _process_mediawiki_dump(root, "sanskrit_wikisource", "sawikisource-latest-pages-articles.xml.bz2", force, limit)


def process_github_oliverhellwig(root: Path, force: bool = False, limit: int | None = None) -> ProcessResult:
    source_id = "github_oliverhellwig"
    raw_dir = root / "data" / "raw" / source_id / "dcs" / "data" / "conllu" / "files"
    output = _output_path(root, source_id, force)
    metadata = _source_metadata(source_id)
    count = 0
    rows = []

    for path in sorted(raw_dir.rglob("*.conllu")):
        text_title, chapter = _read_dcs_file_metadata(path)
        for sentence in _read_conllu_sentences(path):
            text_latn = normalize_text(sentence.get("text", ""))
            if not text_latn:
                continue
            count += 1
            sent_id = sentence.get("sent_id", str(count))
            rows.append(
                {
                    "record_id": f"{source_id}:{sent_id}",
                    "source_id": source_id,
                    "record_type": "dcs_treebank_sentence",
                    "text": transliterate_iast_to_devanagari(text_latn),
                    "text_lang": "sa-Deva",
                    "text_latn": text_latn,
                    "text_latn_scheme": "IAST",
                    "sent_id": sent_id,
                    "title": text_title,
                    "chapter": chapter,
                    "source_path": str(path.relative_to(root / "data" / "raw" / source_id)),
                    "normalization": ["unicode_nfc", "whitespace_squeeze", "iast_to_devanagari"],
                    **metadata,
                }
            )
            if len(rows) >= 5000:
                append_jsonl(output, rows)
                rows = []
            if limit is not None and count >= limit:
                append_jsonl(output, rows)
                return ProcessResult(source_id, "ok", str(output), count)
    append_jsonl(output, rows)
    return ProcessResult(source_id, "ok", str(output), count)


def _read_dcs_file_metadata(path: Path) -> tuple[str | None, str | None]:
    title = None
    chapter = None
    with path.open(encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if line.startswith("# text ="):
                break
            if line.startswith("## text:"):
                title = normalize_text(line.split(":", 1)[1])
            elif line.startswith("## chapter:"):
                chapter = normalize_text(line.split(":", 1)[1])
    return title, chapter


def process_gyaandweep_shabdkosha(root: Path, force: bool = False, limit: int | None = None) -> ProcessResult:
    return _process_single_html_page(root, "gyaandweep_shabdkosha", "shabdkosha.html", "web_lexicon_page", limit, force)


def process_learnsanskrit_grammar(root: Path, force: bool = False, limit: int | None = None) -> ProcessResult:
    return _process_single_html_page(root, "learnsanskrit_grammar", "grammar.html", "web_grammar_page", limit, force)


def _process_single_html_page(
    root: Path,
    source_id: str,
    file_name: str,
    record_type: str,
    limit: int | None,
    force: bool,
) -> ProcessResult:
    raw_path = root / "data" / "raw" / source_id / file_name
    output = _output_path(root, source_id, force)
    metadata = _source_metadata(source_id)
    text = clean_html_text(raw_path.read_text(encoding="utf-8", errors="ignore"))
    if limit == 0 or not text:
        return ProcessResult(source_id, "ok", str(output), 0)
    append_jsonl(
        output,
        [
            {
                "record_id": f"{source_id}:{file_name}",
                "source_id": source_id,
                "record_type": record_type,
                "text": text,
                "text_lang": "mixed",
                "source_path": file_name,
                "normalization": ["unicode_nfc", "html_tag_strip", "whitespace_squeeze"],
                **metadata,
            }
        ],
    )
    return ProcessResult(source_id, "ok", str(output), 1)


def clean_html_text(html: str) -> str:
    html = re.sub(r"(?is)<script\b.*?</script>|<style\b.*?</style>|<svg\b.*?</svg>", " ", html)
    html = re.sub(r"(?is)<br\s*/?>|</p>|</div>|</li>|</h[1-6]>", "\n", html)
    text = re.sub(r"(?is)<[^>]+>", " ", html)
    text = unescape(text)
    lines = [normalize_text(line) for line in text.splitlines()]
    lines = [line for line in lines if line and not _is_navigation_noise(line)]
    return normalize_text("\n".join(lines))


def _is_navigation_noise(line: str) -> bool:
    lowered = line.lower()
    if lowered in {"search", "sign in", "logout", "saved", "languages", "whatsapp", "facebook", "twitter", "telegram", "reddit"}:
        return True
    if len(line) < 3:
        return True
    return False


def _process_mediawiki_dump(
    root: Path,
    source_id: str,
    dump_name: str,
    force: bool,
    limit: int | None,
) -> ProcessResult:
    raw_path = root / "data" / "raw" / source_id / dump_name
    output = _output_path(root, source_id, force)
    metadata = _source_metadata(source_id)
    count = 0
    rows = []

    with bz2.open(raw_path, "rb") as handle:
        for page in _iter_mediawiki_pages(handle):
            if page.get("ns") != "0":
                continue
            text = clean_wikitext(page.get("text", ""))
            if len(text) < 40:
                continue
            count += 1
            rows.append(
                {
                    "record_id": f"{source_id}:{page.get('id', count)}",
                    "source_id": source_id,
                    "record_type": "wiki_page",
                    "title": page.get("title"),
                    "page_id": page.get("id"),
                    "text": text,
                    "text_lang": "sa-Deva",
                    "source_path": dump_name,
                    "normalization": ["unicode_nfc", "whitespace_squeeze", "mediawiki_markup_cleanup"],
                    **metadata,
                }
            )
            if len(rows) >= 1000:
                append_jsonl(output, rows)
                rows = []
            if limit is not None and count >= limit:
                append_jsonl(output, rows)
                return ProcessResult(source_id, "ok", str(output), count)
    append_jsonl(output, rows)
    return ProcessResult(source_id, "ok", str(output), count)


def _iter_mediawiki_pages(handle) -> Iterable[dict[str, str]]:
    ns = {"mw": "http://www.mediawiki.org/xml/export-0.11/"}
    for _, elem in ET.iterparse(handle, events=("end",)):
        if elem.tag.endswith("page"):
            title = elem.findtext("mw:title", default="", namespaces=ns)
            namespace = elem.findtext("mw:ns", default="", namespaces=ns)
            page_id = elem.findtext("mw:id", default="", namespaces=ns)
            text = elem.findtext("mw:revision/mw:text", default="", namespaces=ns)
            yield {"title": title, "ns": namespace, "id": page_id, "text": text}
            elem.clear()


def clean_wikitext(text: str) -> str:
    text = re.sub(r"(?is)<ref[^>/]*/>|<ref[^>]*>.*?</ref>", " ", text)
    text = re.sub(r"(?is)<!--.*?-->", " ", text)
    text = re.sub(r"(?is)\{\{.*?\}\}", " ", text)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[https?://[^\s\]]+\s*([^\]]*)\]", r"\1", text)
    text = re.sub(r"'{2,}", "", text)
    text = re.sub(r"(?m)^\s*[=]{2,}\s*(.*?)\s*[=]{2,}\s*$", r"\1", text)
    text = re.sub(r"(?m)^\s*[\*\#;:]+\s*", "", text)
    text = re.sub(r"(?m)^\s*\{\|.*?$|^\s*\|\}.*?$|^\s*[!|].*$", " ", text)
    return normalize_text(text)


def _read_gretil_tei(path: Path) -> dict[str, str] | None:
    ns = {"tei": "http://www.tei-c.org/ns/1.0"}
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return None

    title_el = root.find(".//tei:titleStmt/tei:title", ns)
    body_el = root.find(".//tei:text/tei:body", ns)
    if body_el is None:
        return None

    text_latn = normalize_text(" ".join(_tei_text_parts(body_el)))
    if not text_latn:
        return None
    return {
        "title": normalize_text(title_el.text or "") if title_el is not None else path.stem,
        "text_latn": text_latn,
    }


def _tei_text_parts(element: ET.Element) -> Iterable[str]:
    tag = element.tag.rsplit("}", 1)[-1]
    if tag in {"head", "note"}:
        return
    if element.text and element.text.strip():
        yield element.text
    for child in element:
        yield from _tei_text_parts(child)
        if child.tail and child.tail.strip():
            yield child.tail
