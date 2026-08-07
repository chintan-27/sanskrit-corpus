from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .manifest import PullRunRecord, SourceRecord, directory_stats, utc_now

USER_AGENT = "sanskrit-corpus/0.1 (+local research acquisition)"


def fetch_bytes(url: str, timeout: int = 60, max_bytes: int = 16 * 1024 * 1024) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise RuntimeError(f"response from {url} exceeds {max_bytes} bytes")
        return data


def fetch_json(url: str, timeout: int = 60) -> object:
    return json.loads(fetch_bytes(url, timeout=timeout).decode("utf-8"))


def fetch_json_pages(url: str, timeout: int = 60) -> list[object]:
    pages: list[object] = []
    next_url: str | None = url
    while next_url:
        request = urllib.request.Request(next_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, list):
                raise RuntimeError(f"unexpected paginated response from {next_url}")
            pages.extend(payload)
            link = response.headers.get("Link", "")
        match = re.search(r'<([^>]+)>;\s*rel="next"', link)
        next_url = match.group(1) if match else None
    return pages


@dataclass(frozen=True)
class PullContext:
    root: Path
    sample: bool
    dry_run: bool
    force: bool


@dataclass(frozen=True)
class DownloadResult:
    byte_count: int
    checksum_sha256: str
    etag: str | None
    last_modified: str | None


def download_file(url: str, destination: Path, timeout: int = 300, max_bytes: int | None = None) -> DownloadResult:
    import hashlib

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.partial")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    digest = hashlib.sha256()
    byte_count = 0
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response, temporary.open("wb") as handle:
            while chunk := response.read(1024 * 1024):
                byte_count += len(chunk)
                if max_bytes is not None and byte_count > max_bytes:
                    raise RuntimeError(f"download from {url} exceeds the {max_bytes}-byte limit")
                digest.update(chunk)
                handle.write(chunk)
            etag = response.headers.get("ETag")
            last_modified = response.headers.get("Last-Modified")
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return DownloadResult(byte_count, digest.hexdigest(), etag, last_modified)


def _staging_directory(target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f".{target.name}.", suffix=".partial", dir=target.parent))


def _publish_directory(staging: Path, target: Path) -> None:
    backup = target.with_name(f".{target.name}.{uuid4().hex}.backup")
    if target.exists():
        target.replace(backup)
    try:
        staging.replace(target)
    except Exception:
        if backup.exists():
            backup.replace(target)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def _safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    root = destination.resolve()
    for member in archive.infolist():
        member_path = Path(member.filename)
        mode = member.external_attr >> 16
        if member_path.is_absolute() or ".." in member_path.parts or (mode & 0o170000) == 0o120000:
            raise RuntimeError(f"unsafe archive member: {member.filename}")
        output = (destination / member_path).resolve()
        if output != root and root not in output.parents:
            raise RuntimeError(f"archive member escapes destination: {member.filename}")
    archive.extractall(destination)


class BaseSource:
    record: SourceRecord

    def pull(self, context: PullContext) -> PullRunRecord:
        raise NotImplementedError

    def _target_dir(self, context: PullContext) -> Path:
        return context.root / "data" / "raw" / self.record.source_id

    def _success_record(self, target: Path, sample: bool) -> PullRunRecord:
        file_count, byte_count, checksum = directory_stats(target)
        (target / "_pull_complete.json").write_text(
            json.dumps(
                {
                    "source_id": self.record.source_id,
                    "file_count": file_count,
                    "byte_count": byte_count,
                    "checksum_sha256": checksum,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return PullRunRecord(
            source_id=self.record.source_id,
            status="ok",
            pulled_at=utc_now(),
            local_path=str(target),
            file_count=file_count,
            byte_count=byte_count,
            checksum_sha256=checksum,
            sample=sample,
        )

    def _failed_record(self, target: Path, error: Exception, sample: bool) -> PullRunRecord:
        return PullRunRecord(
            source_id=self.record.source_id,
            status="failed",
            pulled_at=utc_now(),
            local_path=str(target),
            file_count=0,
            byte_count=0,
            checksum_sha256="",
            error=str(error),
            sample=sample,
        )


class UnavailableSource(BaseSource):
    def __init__(self, record: SourceRecord) -> None:
        self.record = record

    def pull(self, context: PullContext) -> PullRunRecord:
        target = self._target_dir(context)
        return self._failed_record(
            target,
            RuntimeError("source registered for audit only; automated pull is disabled"),
            context.sample,
        )


class GitSource(BaseSource):
    def __init__(self, record: SourceRecord, clone_url: str) -> None:
        self.record = record
        self.clone_url = clone_url

    def pull(self, context: PullContext) -> PullRunRecord:
        target = self._target_dir(context)
        if context.dry_run:
            return PullRunRecord(self.record.source_id, "planned", utc_now(), str(target), 0, 0, "", sample=context.sample)
        if target.exists() and not context.force:
            return self._success_record(target, context.sample)
        staging = _staging_directory(target)
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", self.clone_url, str(staging)],
                check=True,
                capture_output=True,
                text=True,
            )
            revision = subprocess.run(
                ["git", "-C", str(staging), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            _publish_directory(staging, target)
            row = self._success_record(target, context.sample)
            return PullRunRecord(**{**row.__dict__, "source_revision": revision})
        except Exception as exc:  # pragma: no cover - exercised in integration use
            shutil.rmtree(staging, ignore_errors=True)
            return self._failed_record(target, exc, context.sample)


class HuggingFaceDatasetSource(BaseSource):
    def __init__(
        self,
        record: SourceRecord,
        repo_id: str,
        sample_file_limit: int = 8,
        path_prefix: str | None = None,
    ) -> None:
        self.record = record
        self.repo_id = repo_id
        self.sample_file_limit = sample_file_limit
        self.path_prefix = path_prefix.strip("/") if path_prefix else None

    def pull(self, context: PullContext) -> PullRunRecord:
        target = self._target_dir(context)
        if context.dry_run:
            return PullRunRecord(self.record.source_id, "planned", utc_now(), str(target), 0, 0, "", sample=context.sample)
        reuse_existing = False
        if target.exists() and not context.force:
            selection_path = target / "_pull_selection.json"
            selection = json.loads(selection_path.read_text(encoding="utf-8")) if selection_path.exists() else {}
            if context.sample or selection.get("sample") is False:
                return self._success_record(target, context.sample)
            reuse_existing = True
        staging = _staging_directory(target)
        try:
            if reuse_existing:
                shutil.copytree(target, staging, dirs_exist_ok=True)
            tree = self._repo_tree()
            files = [str(entry["path"]) for entry in tree if entry.get("type") == "file" and isinstance(entry.get("path"), str)]
            selected = self._select_files(files, context.sample)
            for remote_path in selected:
                local_path = staging / remote_path
                if not local_path.exists():
                    self._download_file(remote_path, local_path)
            (staging / "_pull_selection.json").write_text(
                json.dumps({"repo_id": self.repo_id, "sample": context.sample, "files": selected}, indent=2),
                encoding="utf-8",
            )
            _publish_directory(staging, target)
            return self._success_record(target, context.sample)
        except Exception as exc:
            shutil.rmtree(staging, ignore_errors=True)
            return self._failed_record(target, exc, context.sample)

    def _repo_tree(self) -> list[dict[str, object]]:
        prefix = f"/{urllib.parse.quote(self.path_prefix, safe='/')}" if self.path_prefix else ""
        url = f"https://huggingface.co/api/datasets/{urllib.parse.quote(self.repo_id, safe='/')}/tree/main{prefix}?recursive=1"
        payload = fetch_json_pages(url)
        return [entry for entry in payload if isinstance(entry, dict)]

    def _select_files(self, files: list[str], sample: bool) -> list[str]:
        if self.path_prefix:
            expected_prefix = f"{self.path_prefix}/"
            files = [path for path in files if path.startswith(expected_prefix)]
        preferred = []
        for path in files:
            name = Path(path).name.lower()
            if name in {"readme.md", "dataset_infos.json", ".gitattributes"}:
                preferred.append(path)
        data_files = [
            path
            for path in files
            if _is_dataset_file(path)
            and path not in preferred
        ]
        selected = preferred + data_files
        if sample:
            return selected[: self.sample_file_limit]
        return selected

    def _download_file(self, remote_path: str, local_path: Path) -> None:
        encoded = urllib.parse.quote(remote_path, safe="/")
        url = f"https://huggingface.co/datasets/{self.repo_id}/resolve/main/{encoded}"
        local_path.parent.mkdir(parents=True, exist_ok=True)
        download_file(url, local_path)


def _is_dataset_file(path: str) -> bool:
    name = path.lower()
    return name.endswith((".json", ".jsonl", ".csv", ".tsv", ".txt", ".parquet", ".jsonl.gz", ".json.gz", ".txt.gz", ".txt.xz"))


class ZipArchiveSource(BaseSource):
    def __init__(self, record: SourceRecord, archive_url: str, archive_name: str) -> None:
        self.record = record
        self.archive_url = archive_url
        self.archive_name = archive_name

    def pull(self, context: PullContext) -> PullRunRecord:
        target = self._target_dir(context)
        if context.dry_run:
            return PullRunRecord(self.record.source_id, "planned", utc_now(), str(target), 0, 0, "", sample=context.sample)
        if target.exists() and not context.force:
            return self._success_record(target, context.sample)
        staging = _staging_directory(target)
        try:
            archive_path = staging / self.archive_name
            download_file(self.archive_url, archive_path)
            extracted_dir = staging / "extracted"
            extracted_dir.mkdir(exist_ok=True)
            with zipfile.ZipFile(archive_path) as archive:
                _safe_extract(archive, extracted_dir)
            _publish_directory(staging, target)
            return self._success_record(target, context.sample)
        except Exception as exc:
            shutil.rmtree(staging, ignore_errors=True)
            return self._failed_record(target, exc, context.sample)


class UrlFileSource(BaseSource):
    def __init__(self, record: SourceRecord, file_url: str, file_name: str) -> None:
        self.record = record
        self.file_url = file_url
        self.file_name = file_name

    def pull(self, context: PullContext) -> PullRunRecord:
        target = self._target_dir(context)
        if context.dry_run:
            return PullRunRecord(self.record.source_id, "planned", utc_now(), str(target), 0, 0, "", sample=context.sample)
        if target.exists() and not context.force:
            return self._success_record(target, context.sample)
        staging = _staging_directory(target)
        try:
            result = download_file(self.file_url, staging / self.file_name)
            _publish_directory(staging, target)
            row = self._success_record(target, context.sample)
            return PullRunRecord(**{**row.__dict__, "etag": result.etag, "last_modified": result.last_modified})
        except Exception as exc:
            shutil.rmtree(staging, ignore_errors=True)
            return self._failed_record(target, exc, context.sample)


def build_sources() -> dict[str, BaseSource]:
    sources: list[BaseSource] = [
        HuggingFaceDatasetSource(
            SourceRecord(
                "sangraha_verified_sanskrit",
                "AI4Bharat Sangraha Verified Sanskrit",
                "https://huggingface.co/datasets/ai4bharat/sangraha/tree/main/verified/san",
                "verified_pretraining_corpus",
                "huggingface_parquet_subset",
                "CC-BY-4.0-dataset; underlying-sources-vary",
                "needs_audit",
                "Human-source verified Sanskrit partition only; synthetic and unverified partitions are excluded.",
            ),
            "ai4bharat/sangraha",
            sample_file_limit=1,
            path_prefix="verified/san",
        ),
        HuggingFaceDatasetSource(
            SourceRecord(
                "sangraha_unverified_sanskrit",
                "AI4Bharat Sangraha Unverified Sanskrit",
                "https://huggingface.co/datasets/ai4bharat/sangraha/tree/main/unverified/san",
                "filtered_web_corpus",
                "huggingface_parquet_subset",
                "CC-BY-4.0-dataset; underlying-sources-vary",
                "needs_audit",
                "Filtered Sanskrit web corpus; kept separate from verified and synthetic partitions.",
            ),
            "ai4bharat/sangraha",
            sample_file_limit=1,
            path_prefix="unverified/san",
        ),
        HuggingFaceDatasetSource(
            SourceRecord(
                "sangraha_synthetic_sanskrit_deva",
                "AI4Bharat Sangraha Synthetic Sanskrit (Devanagari)",
                "https://huggingface.co/datasets/ai4bharat/sangraha/tree/main/synthetic/san_Deva",
                "synthetic_translation_corpus",
                "huggingface_parquet_subset",
                "CC-BY-4.0-dataset; translated-sources-vary",
                "synthetic",
                "English Wikimedia translated with IndicTrans2; Latin transliteration duplicate excluded.",
            ),
            "ai4bharat/sangraha",
            sample_file_limit=1,
            path_prefix="synthetic/san_Deva",
        ),
        HuggingFaceDatasetSource(
            SourceRecord(
                "itihasa",
                "rahular/itihasa",
                "https://huggingface.co/datasets/rahular/itihasa",
                "parallel_corpus",
                "huggingface_dataset",
                "Apache-2.0",
                "releasable",
                "Sanskrit-English parallel corpus; verify attribution in downstream releases.",
            ),
            "rahular/itihasa",
        ),
        HuggingFaceDatasetSource(
            SourceRecord(
                "pe_ocr_sanskrit",
                "Sanskrit Post-OCR Correction",
                "https://huggingface.co/datasets/acomquest/sanskrit-ocr-post-correction",
                "real_post_ocr_pairs",
                "huggingface_dataset",
                "MIT-dataset; underlying-editions-require-audit",
                "needs_audit",
                "Real OCR and corrected Sanskrit sentence pairs; preserve upstream splits and audit the 30 source editions.",
            ),
            "acomquest/sanskrit-ocr-post-correction",
        ),
        HuggingFaceDatasetSource(
            SourceRecord(
                "roundtrip_ocr_sanskrit",
                "RoundTripOCR Sanskrit",
                "https://huggingface.co/datasets/cfilt/RoundTripOCR-sanskrit",
                "synthetic_post_ocr_pairs",
                "huggingface_dataset",
                "Apache-2.0",
                "synthetic",
                "Synthetic OCR/corrected pairs generated across fonts; never mix with real OCR evaluation data.",
            ),
            "cfilt/RoundTripOCR-sanskrit",
        ),
        HuggingFaceDatasetSource(
            SourceRecord(
                "fineweb2_sanskrit_deva",
                "FineWeb 2 Sanskrit Devanagari",
                "https://huggingface.co/datasets/HuggingFaceFW/fineweb-2/tree/main/data/san_Deva/train",
                "filtered_web_corpus",
                "huggingface_parquet_subset",
                "ODC-BY-1.0; Common-Crawl-source-terms",
                "needs_audit",
                "Sanskrit Devanagari subset only; retain URL provenance and deduplicate against other web corpora.",
            ),
            "HuggingFaceFW/fineweb-2",
            sample_file_limit=1,
            path_prefix="data/san_Deva/train",
        ),
        HuggingFaceDatasetSource(
            SourceRecord(
                "madlad400_sanskrit",
                "MADLAD-400 Sanskrit",
                "https://huggingface.co/datasets/allenai/MADLAD-400/tree/main/data/sa",
                "web_corpus_clean_and_noisy",
                "huggingface_jsonl_subset",
                "ODC-BY-1.0; Common-Crawl-source-terms",
                "needs_audit",
                "Sanskrit clean and noisy shards; keep variants separate and retain URL-level provenance.",
            ),
            "allenai/MADLAD-400",
            sample_file_limit=1,
            path_prefix="data/sa",
        ),
        HuggingFaceDatasetSource(
            SourceRecord(
                "process_venue_sanskrit_ocr",
                "Process Venue Sanskrit OCR Typed Dataset",
                "https://huggingface.co/datasets/Process-Venue/Sanskrit-OCR-Typed-Dataset",
                "ocr_image_text_pairs",
                "huggingface_dataset",
                "MIT-dataset; image-origins-require-audit",
                "needs_audit",
                "Sanskrit image/transcription pairs; audit image origins and preserve upstream splits.",
            ),
            "Process-Venue/Sanskrit-OCR-Typed-Dataset",
        ),
        HuggingFaceDatasetSource(
            SourceRecord(
                "naamah",
                "akhil2808/Naamah",
                "https://huggingface.co/datasets/akhil2808/Naamah",
                "ner_benchmark",
                "huggingface_dataset",
                "MIT",
                "benchmark",
                "Sanskrit NER benchmark; sample label quality before training use.",
            ),
            "akhil2808/Naamah",
        ),
        HuggingFaceDatasetSource(
            SourceRecord(
                "samhitika_0_0_1",
                "khoomeik/samhitika-0.0.1",
                "https://huggingface.co/datasets/khoomeik/samhitika-0.0.1",
                "synthetic_corpus",
                "huggingface_dataset",
                "MIT",
                "synthetic",
                "Synthetic translation corpus; known quality risks and Hindi contamination.",
            ),
            "khoomeik/samhitika-0.0.1",
        ),
        GitSource(
            SourceRecord(
                "ud_sanskrit_vedic",
                "UniversalDependencies/UD_Sanskrit-Vedic",
                "https://github.com/UniversalDependencies/UD_Sanskrit-Vedic",
                "treebank",
                "git_clone",
                "CC-BY-SA-4.0",
                "releasable",
                "Vedic Sanskrit Universal Dependencies treebank; attribution and ShareAlike required.",
            ),
            "https://github.com/UniversalDependencies/UD_Sanskrit-Vedic.git",
        ),
        GitSource(
            SourceRecord(
                "ud_sanskrit_ufal",
                "UniversalDependencies/UD_Sanskrit-UFAL",
                "https://github.com/UniversalDependencies/UD_Sanskrit-UFAL",
                "treebank",
                "git_clone",
                "CC-BY-SA-4.0",
                "releasable",
                "Classical Sanskrit dependency treebank; preserve attribution and official evaluation splits.",
            ),
            "https://github.com/UniversalDependencies/UD_Sanskrit-UFAL.git",
        ),
        GitSource(
            SourceRecord(
                "github_oliverhellwig",
                "OliverHellwig/sanskrit",
                "https://github.com/OliverHellwig/sanskrit",
                "github_repository",
                "git_clone",
                "CC-BY-4.0",
                "releasable",
                "DCS CoNLL-U data is licensed CC BY 4.0; preserve attribution.",
            ),
            "https://github.com/OliverHellwig/sanskrit.git",
        ),
        GitSource(
            SourceRecord(
                "sarit_corpus",
                "sarit/SARIT-corpus",
                "https://github.com/sarit/SARIT-corpus",
                "tei_corpus",
                "git_clone",
                "needs_audit",
                "needs_audit",
                "Scholarly Indic TEI corpus; audit per-file license and headers before release.",
            ),
            "https://github.com/sarit/SARIT-corpus.git",
        ),
        GitSource(
            SourceRecord(
                "saamayik",
                "ayushbits/saamayik",
                "https://github.com/ayushbits/saamayik",
                "parallel_corpus",
                "git_clone",
                "needs_audit",
                "needs_audit",
                "English-Sanskrit modern prose translation dataset; audit repository license before release.",
            ),
            "https://github.com/ayushbits/saamayik.git",
        ),
        ZipArchiveSource(
            SourceRecord(
                "gretil_sanskrit",
                "GRETIL Sanskrit cumulative download",
                "https://gretil.sub.uni-goettingen.de/gretil.html",
                "text_archive",
                "zip_download",
                "CC-BY-NC-SA-4.0",
                "restricted",
                "Current TEI archive declares CC BY-NC-SA 4.0; exclude from releasable exports.",
            ),
            "https://gretil.sub.uni-goettingen.de/gretil/1_sanskr.zip",
            "1_sanskr.zip",
        ),
        UrlFileSource(
            SourceRecord(
                "sanskrit_wikipedia",
                "Sanskrit Wikipedia dump",
                "https://dumps.wikimedia.org/sawiki/latest/",
                "wikimedia_dump",
                "url_download",
                "CC-BY-SA-4.0",
                "releasable",
                "Sanskrit Wikipedia latest pages-articles dump; Wikimedia attribution and ShareAlike required.",
            ),
            "https://dumps.wikimedia.org/sawiki/latest/sawiki-latest-pages-articles.xml.bz2",
            "sawiki-latest-pages-articles.xml.bz2",
        ),
        UrlFileSource(
            SourceRecord(
                "sanskrit_wikisource",
                "Sanskrit Wikisource dump",
                "https://dumps.wikimedia.org/sawikisource/latest/",
                "wikimedia_dump",
                "url_download",
                "CC-BY-SA-4.0",
                "needs_audit",
                "Sanskrit Wikisource latest pages-articles dump; page/source-level audit required before release.",
            ),
            "https://dumps.wikimedia.org/sawikisource/latest/sawikisource-latest-pages-articles.xml.bz2",
            "sawikisource-latest-pages-articles.xml.bz2",
        ),
        UrlFileSource(
            SourceRecord(
                "sanskrit_wiktionary",
                "Sanskrit Wiktionary dump",
                "https://dumps.wikimedia.org/sawiktionary/latest/",
                "wikimedia_lexical_dump",
                "url_download",
                "CC-BY-SA-4.0",
                "releasable",
                "Sanskrit lexical entries and examples; preserve revision attribution and ShareAlike requirements.",
            ),
            "https://dumps.wikimedia.org/sawiktionary/latest/sawiktionary-latest-pages-articles.xml.bz2",
            "sawiktionary-latest-pages-articles.xml.bz2",
        ),
        UrlFileSource(
            SourceRecord(
                "cc100_sanskrit",
                "CC-100 Sanskrit",
                "https://data.statmt.org/cc-100/",
                "common_crawl_monolingual",
                "url_download",
                "research-corpus; Common-Crawl-source-terms",
                "needs_audit",
                "Sanskrit Common Crawl extraction; deduplicate against FineWeb, CulturaX, MADLAD, and Sangraha.",
            ),
            "https://data.statmt.org/cc-100/sa.txt.xz",
            "sa.txt.xz",
        ),
        UrlFileSource(
            SourceRecord(
                "gyaandweep_shabdkosha",
                "Gyaandweep śabda kośaḥ",
                "https://gyaandweep.com/learn/sanskrit/shabdkosha/",
                "web_lexicon",
                "url_download",
                "needs_audit",
                "needs_audit",
                "Sanskrit vocabulary/dictionary page; site terms and extraction quality need review.",
            ),
            "https://gyaandweep.com/learn/sanskrit/shabdkosha/",
            "shabdkosha.html",
        ),
        UrlFileSource(
            SourceRecord(
                "learnsanskrit_grammar",
                "Learn Sanskrit grammar",
                "https://learnsanskrit.org/grammar/",
                "web_grammar",
                "url_download",
                "CC-NC-SA-1.0",
                "restricted",
                "Grammar guide index and lessons; NonCommercial ShareAlike terms prevent clean releasable export.",
            ),
            "https://learnsanskrit.org/grammar/",
            "grammar.html",
        ),
        UnavailableSource(
            SourceRecord(
                "kaggle_sanskrit_text_corpus",
                "Sanskrit Text Corpus for LLM Pre-Training",
                "https://www.kaggle.com/datasets/preetsojitra/sanskrit-text-corpus",
                "kaggle_dataset",
                "manual_or_kaggle_credentials",
                "needs_audit",
                "needs_audit",
                "Requires Kaggle metadata/license verification before automated pull.",
            )
        ),
        UnavailableSource(
            SourceRecord(
                "culturax_sanskrit",
                "CulturaX Sanskrit",
                "https://huggingface.co/datasets/uonlp/CulturaX",
                "filtered_web_corpus",
                "gated_huggingface_dataset",
                "mC4-and-OSCAR-upstream-terms",
                "needs_audit",
                "Requires accepting Hugging Face access conditions and authentication; Sanskrit configuration is sa.",
            )
        ),
        UnavailableSource(
            SourceRecord(
                "aikosh_sanskrit_post_ocr",
                "AIKosh Sanskrit post-OCR correction dataset",
                "https://aikosh.indiaai.gov.in/home/datasets/details/a_benchmark_and_dataset_for_post_ocr_text_correction_in_sanskrit.html",
                "ocr_benchmark",
                "manual_aikosh_verification",
                "needs_audit",
                "needs_audit",
                "Access terms and downloadable artifacts need manual verification.",
            )
        ),
        UnavailableSource(
            SourceRecord(
                "aikosh_aksharantar",
                "Aksharantar",
                "https://aikosh.indiaai.gov.in/home/datasets/details/aksharantar.html",
                "transliteration_dataset",
                "manual_aikosh_verification",
                "CC-BY-SA-4.0",
                "needs_audit",
                "Register first; confirm AIKosh download flow before automated pull.",
            )
        ),
    ]
    return {source.record.source_id: source for source in sources}
