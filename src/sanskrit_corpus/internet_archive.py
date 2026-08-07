from __future__ import annotations

import gzip
import hashlib
import json
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .manifest import append_jsonl, utc_now
from .sources import download_file, fetch_json

DEFAULT_IA_QUERY = "sanskrit AND mediatype:texts"


@dataclass(frozen=True)
class IaPullResult:
    status: str
    item_count: int
    file_count: int
    byte_count: int
    manifest_path: str


@dataclass(frozen=True)
class IaCompactResult:
    item_count: int
    text_file_count: int
    removed_file_count: int
    removed_bytes: int
    manifest_path: str


def pull_internet_archive(
    root: Path,
    query: str = DEFAULT_IA_QUERY,
    limit: int | None = 25,
    max_gb: float | None = 1.0,
    file_kind: str = "ocr_text",
    compact_text: bool = False,
    catalog_path: Path | None = None,
    shard_count: int = 1,
    shard_index: int = 0,
) -> IaPullResult:
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative")
    if max_gb is not None and max_gb < 0:
        raise ValueError("max_gb must be non-negative")
    if shard_count < 1 or not 0 <= shard_index < shard_count:
        raise ValueError("shard_index must be between zero and shard_count - 1")
    max_bytes = int(max_gb * 1024 * 1024 * 1024) if max_gb is not None else None
    target_root = root / "data" / "raw" / "internet_archive"
    manifest_name = "internet_archive_pulls.jsonl" if shard_count == 1 else f"internet_archive_pulls_shard_{shard_index:03d}.jsonl"
    manifest_path = root / "data" / "manifests" / manifest_name
    target_root.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    item_count = 0
    file_count = 0
    byte_count = 0
    items = load_census_items(catalog_path, require_ocr=True) if catalog_path else search_items(query, limit)
    selected_items = items[:limit] if limit is not None else items
    for item in selected_items[shard_index::shard_count]:
        identifier = _safe_component(str(item["identifier"]))
        item_count += 1
        try:
            metadata = item_metadata(identifier)
        except Exception as exc:
            row = _manifest_row(identifier, {"name": "_metadata.json"}, f"failed:{exc}", target_root / identifier, 0)
            append_jsonl(manifest_path, [row])
            continue
        selected = select_files(metadata.get("files", []), file_kind)
        item_dir = target_root / identifier
        item_dir.mkdir(parents=True, exist_ok=True)
        (item_dir / "_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

        for file_info in selected:
            size = int(file_info.get("size") or 0)
            if max_bytes is not None and size and byte_count + size > max_bytes:
                append_jsonl(manifest_path, [_manifest_row(identifier, file_info, "skipped_quota", item_dir, 0)])
                continue
            name = str(file_info["name"])
            _validate_relative_path(name)
            local_path = _bounded_local_path(item_dir, name)
            compacted_path = local_path.with_suffix(local_path.suffix + ".gz")
            if compact_text and compacted_path.exists():
                downloaded = compacted_path.stat().st_size
                byte_count += downloaded
                file_count += 1
                append_jsonl(
                    manifest_path,
                    [_manifest_row(identifier, file_info, "already_compacted", item_dir, downloaded)],
                )
                continue
            if local_path.exists():
                downloaded = local_path.stat().st_size
            else:
                local_path.parent.mkdir(parents=True, exist_ok=True)
                remaining = max_bytes - byte_count if max_bytes is not None else None
                url = f"https://archive.org/download/{urllib.parse.quote(identifier)}/{urllib.parse.quote(name)}"
                try:
                    result = download_file(url, local_path, timeout=300, max_bytes=remaining)
                except Exception as exc:
                    append_jsonl(manifest_path, [_manifest_row(identifier, file_info, f"failed:{exc}", item_dir, 0)])
                    continue
                downloaded = result.byte_count
            byte_count += downloaded
            file_count += 1
            row = _manifest_row(identifier, file_info, "ok", item_dir, downloaded)
            if compact_text and _is_ocr_text(local_path):
                compacted_path, digest = compact_text_file(local_path)
                row.update({"status": "ok_compacted", "local_path": str(compacted_path), "sha256": digest})
            append_jsonl(manifest_path, [row])
        if max_bytes is not None and byte_count >= max_bytes:
            break

    return IaPullResult("ok", item_count, file_count, byte_count, str(manifest_path))


def load_census_items(path: Path, require_ocr: bool = False, require_pdf_without_ocr: bool = False) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as source:
        for line in source:
            item = json.loads(line)
            if not isinstance(item, dict) or not item.get("identifier"):
                continue
            if require_ocr and not item.get("has_ocr"):
                continue
            if require_pdf_without_ocr and not (item.get("has_usable_pdf") and not item.get("has_ocr")):
                continue
            items.append(item)
    return items


def compact_internet_archive(root: Path, delete_source_artifacts: bool = False) -> IaCompactResult:
    target_root = root / "data" / "raw" / "internet_archive"
    manifest_path = root / "data" / "manifests" / "internet_archive_compaction.jsonl"
    item_count = 0
    text_file_count = 0
    removed_file_count = 0
    removed_bytes = 0

    for item_dir in sorted(path for path in target_root.iterdir() if path.is_dir()):
        item_count += 1
        preserved_text = False
        for path in sorted(item_dir.rglob("*")):
            if not path.is_file() or not _is_ocr_text(path):
                continue
            original_size = path.stat().st_size
            compacted_path, digest = compact_text_file(path)
            preserved_text = True
            text_file_count += 1
            removed_file_count += 1
            removed_bytes += original_size
            append_jsonl(
                manifest_path,
                [{
                    "source_id": "internet_archive",
                    "identifier": item_dir.name,
                    "status": "ok_compacted",
                    "source_file": str(path.relative_to(item_dir)),
                    "local_path": str(compacted_path),
                    "uncompressed_bytes": original_size,
                    "compressed_bytes": compacted_path.stat().st_size,
                    "sha256": digest,
                    "compacted_at": utc_now(),
                    "release_status": "needs_audit",
                }],
            )
        if delete_source_artifacts and preserved_text:
            for path in sorted(item_dir.rglob("*")):
                if not path.is_file() or path.name == "_metadata.json" or path.name.endswith(".txt.gz"):
                    continue
                size = path.stat().st_size
                path.unlink()
                removed_file_count += 1
                removed_bytes += size

    return IaCompactResult(item_count, text_file_count, removed_file_count, removed_bytes, str(manifest_path))


def compact_text_file(path: Path) -> tuple[Path, str]:
    destination = path.with_name(f"{path.name}.gz")
    temporary = destination.with_name(f"{destination.name}.partial")
    digest = hashlib.sha256()
    with path.open("rb") as source, gzip.open(temporary, "wb", compresslevel=6) as output:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
            output.write(chunk)
    verification_digest = hashlib.sha256()
    with gzip.open(temporary, "rb") as verification:
        while chunk := verification.read(1024 * 1024):
            verification_digest.update(chunk)
    if verification_digest.digest() != digest.digest():
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"gzip verification failed for {path}")
    temporary.replace(destination)
    path.unlink()
    return destination, digest.hexdigest()


def _is_ocr_text(path: Path) -> bool:
    name = path.name.lower()
    return name.endswith(("_djvu.txt", "_text.txt"))


def search_items(query: str, limit: int | None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page = 1
    page_size = min(limit, 1000) if limit is not None else 1000
    while limit is None or len(items) < limit:
        rows = min(page_size, limit - len(items)) if limit is not None else page_size
        params = urllib.parse.urlencode(
            {
                "q": query,
                "fl[]": ["identifier", "title"],
                "rows": str(rows),
                "page": str(page),
                "output": "json",
            },
            doseq=True,
        )
        payload = fetch_json(f"https://archive.org/advancedsearch.php?{params}", timeout=120)
        response = payload.get("response", {}) if isinstance(payload, dict) else {}
        docs = response.get("docs", []) if isinstance(response, dict) else []
        if not isinstance(docs, list) or not docs:
            break
        items.extend(item for item in docs if isinstance(item, dict))
        if len(items) >= int(response.get("numFound") or 0):
            break
        page += 1
    return items[:limit] if limit is not None else items


def item_metadata(identifier: str) -> dict[str, Any]:
    payload = fetch_json(f"https://archive.org/metadata/{urllib.parse.quote(identifier)}", timeout=120)
    if not isinstance(payload, dict):
        raise RuntimeError(f"unexpected metadata response for {identifier}")
    return payload


def select_files(files: list[dict[str, Any]], file_kind: str) -> list[dict[str, Any]]:
    suffixes: tuple[str, ...]
    if file_kind == "ocr_text":
        suffixes = ("_djvu.txt", "_text.txt")
    elif file_kind == "pdf":
        suffixes = (".pdf",)
    elif file_kind == "all":
        suffixes = ("_djvu.txt", "_text.txt", ".pdf", ".djvu", ".epub")
    else:
        raise ValueError("file_kind must be one of: ocr_text, pdf, all")
    return [file_info for file_info in files if str(file_info.get("name", "")).lower().endswith(suffixes)]


def _manifest_row(identifier: str, file_info: dict[str, Any], status: str, item_dir: Path, downloaded: int) -> dict[str, Any]:
    return {
        "source_id": "internet_archive",
        "identifier": identifier,
        "file_name": file_info.get("name"),
        "status": status,
        "declared_size": int(file_info.get("size") or 0),
        "downloaded_bytes": downloaded,
        "local_dir": str(item_dir),
        "pulled_at": utc_now(),
        "release_status": "needs_audit",
    }


def _safe_component(value: str) -> str:
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError(f"unsafe path component: {value!r}")
    return value


def _validate_relative_path(value: str) -> None:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not value:
        raise ValueError(f"unsafe relative path: {value!r}")


def _bounded_local_path(item_dir: Path, name: str, max_name_bytes: int = 180) -> Path:
    """Keep IA filenames below common filesystem component limits."""
    path = Path(name)
    if len(path.name.encode("utf-8")) <= max_name_bytes:
        return item_dir / path
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]
    suffixes = "".join(path.suffixes)
    budget = max_name_bytes - len(f".{digest}{suffixes}".encode())
    stem = path.name[:budget]
    while len(stem.encode("utf-8")) > budget:
        stem = stem[:-1]
    return item_dir / path.parent / f"{stem}.{digest}{suffixes}"
