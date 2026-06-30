from __future__ import annotations

import json
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .manifest import PullRunRecord, SourceRecord, directory_stats, utc_now


USER_AGENT = "sanskrit-corpus/0.1 (+local research acquisition)"


def fetch_bytes(url: str, timeout: int = 60) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def fetch_json(url: str, timeout: int = 60) -> object:
    return json.loads(fetch_bytes(url, timeout=timeout).decode("utf-8"))


@dataclass(frozen=True)
class PullContext:
    root: Path
    sample: bool
    dry_run: bool
    force: bool


class BaseSource:
    record: SourceRecord

    def pull(self, context: PullContext) -> PullRunRecord:
        raise NotImplementedError

    def _target_dir(self, context: PullContext) -> Path:
        return context.root / "data" / "raw" / self.record.source_id

    def _success_record(self, target: Path, sample: bool) -> PullRunRecord:
        file_count, byte_count, checksum = directory_stats(target)
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
        if target.exists():
            if not context.force:
                return self._success_record(target, context.sample)
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", self.clone_url, str(target)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return self._success_record(target, context.sample)
        except Exception as exc:  # pragma: no cover - exercised in integration use
            return self._failed_record(target, exc, context.sample)


class HuggingFaceDatasetSource(BaseSource):
    def __init__(self, record: SourceRecord, repo_id: str, sample_file_limit: int = 8) -> None:
        self.record = record
        self.repo_id = repo_id
        self.sample_file_limit = sample_file_limit

    def pull(self, context: PullContext) -> PullRunRecord:
        target = self._target_dir(context)
        if context.dry_run:
            return PullRunRecord(self.record.source_id, "planned", utc_now(), str(target), 0, 0, "", sample=context.sample)
        if target.exists():
            if not context.force:
                return self._success_record(target, context.sample)
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)
        try:
            tree = self._repo_tree()
            files = [entry["path"] for entry in tree if entry.get("type") == "file"]
            selected = self._select_files(files, context.sample)
            for remote_path in selected:
                self._download_file(remote_path, target / remote_path)
            (target / "_pull_selection.json").write_text(
                json.dumps({"repo_id": self.repo_id, "sample": context.sample, "files": selected}, indent=2),
                encoding="utf-8",
            )
            return self._success_record(target, context.sample)
        except Exception as exc:
            return self._failed_record(target, exc, context.sample)

    def _repo_tree(self) -> list[dict[str, object]]:
        url = f"https://huggingface.co/api/datasets/{urllib.parse.quote(self.repo_id, safe='/')}/tree/main?recursive=1"
        payload = fetch_json(url)
        if not isinstance(payload, list):
            raise RuntimeError(f"unexpected Hugging Face tree response for {self.repo_id}")
        return [entry for entry in payload if isinstance(entry, dict)]

    def _select_files(self, files: list[str], sample: bool) -> list[str]:
        preferred = []
        for path in files:
            name = Path(path).name.lower()
            if name in {"readme.md", "dataset_infos.json", ".gitattributes"}:
                preferred.append(path)
        data_files = [
            path
            for path in files
            if Path(path).suffix.lower() in {".json", ".jsonl", ".csv", ".tsv", ".txt", ".parquet"}
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
        local_path.write_bytes(fetch_bytes(url))


class ZipArchiveSource(BaseSource):
    def __init__(self, record: SourceRecord, archive_url: str, archive_name: str) -> None:
        self.record = record
        self.archive_url = archive_url
        self.archive_name = archive_name

    def pull(self, context: PullContext) -> PullRunRecord:
        target = self._target_dir(context)
        if context.dry_run:
            return PullRunRecord(self.record.source_id, "planned", utc_now(), str(target), 0, 0, "", sample=context.sample)
        if target.exists():
            if not context.force:
                return self._success_record(target, context.sample)
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)
        try:
            archive_path = target / self.archive_name
            archive_path.write_bytes(fetch_bytes(self.archive_url, timeout=300))
            extracted_dir = target / "extracted"
            extracted_dir.mkdir(exist_ok=True)
            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(extracted_dir)
            return self._success_record(target, context.sample)
        except Exception as exc:
            return self._failed_record(target, exc, context.sample)


def build_sources() -> dict[str, BaseSource]:
    sources: list[BaseSource] = [
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
                "github_oliverhellwig",
                "OliverHellwig/sanskrit",
                "https://github.com/OliverHellwig/sanskrit",
                "github_repository",
                "git_clone",
                "needs_audit",
                "needs_audit",
                "DCS-associated Sanskrit repository; audit repo license and source terms before release.",
            ),
            "https://github.com/OliverHellwig/sanskrit.git",
        ),
        ZipArchiveSource(
            SourceRecord(
                "gretil_sanskrit",
                "GRETIL Sanskrit cumulative download",
                "https://gretil.sub.uni-goettingen.de/gretil.html",
                "text_archive",
                "zip_download",
                "needs_audit",
                "needs_audit",
                "Cumulative Sanskrit archive; item-level source and license audit required before release.",
            ),
            "https://gretil.sub.uni-goettingen.de/gretil/1_sanskr.zip",
            "1_sanskr.zip",
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
