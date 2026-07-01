from __future__ import annotations

import json
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .manifest import append_jsonl, utc_now
from .sources import fetch_bytes, fetch_json


DEFAULT_IA_QUERY = "sanskrit AND mediatype:texts"


@dataclass(frozen=True)
class IaPullResult:
    status: str
    item_count: int
    file_count: int
    byte_count: int
    manifest_path: str


def pull_internet_archive(
    root: Path,
    query: str = DEFAULT_IA_QUERY,
    limit: int = 25,
    max_gb: float = 1.0,
    file_kind: str = "ocr_text",
) -> IaPullResult:
    max_bytes = int(max_gb * 1024 * 1024 * 1024)
    target_root = root / "data" / "raw" / "internet_archive"
    manifest_path = root / "data" / "manifests" / "internet_archive_pulls.jsonl"
    target_root.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    item_count = 0
    file_count = 0
    byte_count = 0
    rows = []

    for item in search_items(query, limit):
        identifier = item["identifier"]
        item_count += 1
        metadata = item_metadata(identifier)
        selected = select_files(metadata.get("files", []), file_kind)
        item_dir = target_root / identifier
        item_dir.mkdir(parents=True, exist_ok=True)
        (item_dir / "_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

        for file_info in selected:
            size = int(file_info.get("size") or 0)
            if size and byte_count + size > max_bytes:
                rows.append(_manifest_row(identifier, file_info, "skipped_quota", item_dir, 0))
                continue
            name = file_info["name"]
            local_path = item_dir / name
            if local_path.exists():
                downloaded = local_path.stat().st_size
            else:
                local_path.parent.mkdir(parents=True, exist_ok=True)
                url = f"https://archive.org/download/{urllib.parse.quote(identifier)}/{urllib.parse.quote(name)}"
                try:
                    data = fetch_bytes(url, timeout=300)
                except Exception as exc:
                    rows.append(_manifest_row(identifier, file_info, f"failed:{exc}", item_dir, 0))
                    continue
                local_path.write_bytes(data)
                downloaded = len(data)
            byte_count += downloaded
            file_count += 1
            rows.append(_manifest_row(identifier, file_info, "ok", item_dir, downloaded))
        if byte_count >= max_bytes:
            break

    append_jsonl(manifest_path, rows)
    return IaPullResult("ok", item_count, file_count, byte_count, str(manifest_path))


def search_items(query: str, limit: int) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "q": query,
            "fl[]": ["identifier", "title"],
            "rows": str(limit),
            "page": "1",
            "output": "json",
        },
        doseq=True,
    )
    payload = fetch_json(f"https://archive.org/advancedsearch.php?{params}", timeout=120)
    return payload.get("response", {}).get("docs", []) if isinstance(payload, dict) else []


def item_metadata(identifier: str) -> dict[str, Any]:
    payload = fetch_json(f"https://archive.org/metadata/{urllib.parse.quote(identifier)}", timeout=120)
    if not isinstance(payload, dict):
        raise RuntimeError(f"unexpected metadata response for {identifier}")
    return payload


def select_files(files: list[dict[str, Any]], file_kind: str) -> list[dict[str, Any]]:
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
