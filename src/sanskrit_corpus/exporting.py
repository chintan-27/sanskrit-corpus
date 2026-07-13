from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from .licensing import apply_license, resolve_license
from .manifest import file_stats, utc_now

PROFILE_STATUSES = {
    "releasable": {"releasable"},
    "clean_releasable": {"releasable"},
    "benchmark": {"benchmark"},
    "synthetic": {"synthetic"},
    "needs_audit": {"needs_audit"},
    "all": {"releasable", "benchmark", "synthetic", "needs_audit", "restricted"},
}

CLEAN_PROFILES = {"clean_releasable"}


def audit_processed(root: Path) -> dict[str, Any]:
    processed_dir = root / "data" / "processed"
    by_status: Counter[str] = Counter()
    by_source: dict[str, Counter[str]] = defaultdict(Counter)
    by_license: Counter[str] = Counter()
    metadata_drift: Counter[str] = Counter()
    files = []

    for path in sorted(processed_dir.glob("*.jsonl")):
        record_count = 0
        source_id = path.stem
        for embedded in _read_jsonl(path):
            row = apply_license(root, embedded)
            record_count += 1
            status = row.get("release_status", "missing")
            license_label = row.get("license_label", "missing")
            by_status[status] += 1
            by_source[source_id][status] += 1
            by_license[license_label] += 1
            if row.get("license_label") != embedded.get("license_label") or row.get("release_status") != embedded.get("release_status"):
                metadata_drift[source_id] += 1
        files.append({"source_id": source_id, "record_count": record_count, "byte_count": path.stat().st_size})

    return {
        "by_status": dict(sorted(by_status.items())),
        "by_license": dict(sorted(by_license.items())),
        "by_source": {source_id: dict(statuses) for source_id, statuses in sorted(by_source.items())},
        "files": files,
        "effective_metadata_drift": dict(sorted(metadata_drift.items())),
    }


def write_audit(root: Path) -> Path:
    path = root / "data" / "reports" / "audit_summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(json.dumps(audit_processed(root), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)
    return path


def export_profile(root: Path, profile: str, force: bool = False) -> tuple[Path, int]:
    if profile not in PROFILE_STATUSES:
        known = ", ".join(sorted(PROFILE_STATUSES))
        raise ValueError(f"unknown export profile '{profile}'. Known profiles: {known}")

    output = root / "data" / "releases" / f"{profile}.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not force:
        raise FileExistsError(f"{output} already exists; pass --force to replace it")

    from .validation import validate_processed, write_validation_report

    validation = validate_processed(root, profile=profile)
    validation_path = write_validation_report(root, validation, f"validation_{profile}.json")
    if validation["status"] != "ok":
        error_count = validation["counts"].get("error", 0)
        raise ValueError(f"export blocked by {error_count} validation errors; see {validation_path}")

    allowed = PROFILE_STATUSES[profile]
    count = 0
    seen_text: set[str] = set()
    temporary = output.with_name(f".{output.name}.{uuid4().hex}.tmp")
    attributions: dict[tuple[str, str], dict[str, Any]] = {}
    process_run_ids: set[str] = set()
    try:
        with temporary.open("w", encoding="utf-8") as out:
            for path in sorted((root / "data" / "processed").glob("*.jsonl")):
                for embedded in _read_jsonl(path):
                    row = apply_license(root, embedded)
                    decision = resolve_license(root, embedded)
                    source_id = str(row.get("source_id", ""))
                    if row.get("release_status") not in allowed:
                        continue
                    attributions[(source_id, decision.license_label)] = {
                        "source_id": source_id,
                        "license_label": decision.license_label,
                        "attribution": decision.attribution,
                        "evidence_url": decision.evidence_url,
                    }
                    if row.get("processing_run_id"):
                        process_run_ids.add(str(row["processing_run_id"]))
                    if profile in CLEAN_PROFILES:
                        if not is_clean_record(row):
                            continue
                        key = _dedupe_key(row)
                        if key in seen_text:
                            continue
                        seen_text.add(key)
                    out.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
                    out.write("\n")
                    count += 1
        temporary.replace(output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    byte_count, checksum = file_stats(output)
    validation_bytes, validation_checksum = file_stats(validation_path)
    manifest = {
        "profile": profile,
        "created_at": utc_now(),
        "record_count": count,
        "byte_count": byte_count,
        "checksum_sha256": checksum,
        "validation": {"path": str(validation_path), "byte_count": validation_bytes, "checksum_sha256": validation_checksum},
        "processing_run_ids": sorted(process_run_ids),
        "attributions": [attributions[key] for key in sorted(attributions)],
    }
    manifest_path = output.with_suffix(".manifest.json")
    manifest_temporary = manifest_path.with_name(f".{manifest_path.name}.{uuid4().hex}.tmp")
    manifest_temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    manifest_temporary.replace(manifest_path)
    return output, count


def _read_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def is_clean_record(row: dict[str, Any]) -> bool:
    text = str(row.get("text") or "").strip()
    if len(text) < 40:
        return False
    if "#REDIRECT" in text.upper() or "{{" in text or "[[" in text:
        return False
    if str(row.get("text_lang", "")).startswith("sa") and _devanagari_ratio(text) < 0.45:
        return False
    return True


def _dedupe_key(row: dict[str, Any]) -> str:
    return " ".join(str(row.get("text") or "").lower().split())


def _devanagari_ratio(text: str) -> float:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return 0.0
    devanagari = sum(1 for char in letters if "\u0900" <= char <= "\u097f")
    return devanagari / len(letters)
