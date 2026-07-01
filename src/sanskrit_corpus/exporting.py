from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PROFILE_STATUSES = {
    "releasable": {"releasable"},
    "benchmark": {"benchmark"},
    "synthetic": {"synthetic"},
    "needs_audit": {"needs_audit"},
    "all": {"releasable", "benchmark", "synthetic", "needs_audit", "restricted"},
}


def audit_processed(root: Path) -> dict[str, Any]:
    processed_dir = root / "data" / "processed"
    by_status: Counter[str] = Counter()
    by_source: dict[str, Counter[str]] = defaultdict(Counter)
    by_license: Counter[str] = Counter()
    files = []

    for path in sorted(processed_dir.glob("*.jsonl")):
        record_count = 0
        source_id = path.stem
        for row in _read_jsonl(path):
            record_count += 1
            status = row.get("release_status", "missing")
            license_label = row.get("license_label", "missing")
            by_status[status] += 1
            by_source[source_id][status] += 1
            by_license[license_label] += 1
        files.append({"source_id": source_id, "record_count": record_count, "byte_count": path.stat().st_size})

    return {
        "by_status": dict(sorted(by_status.items())),
        "by_license": dict(sorted(by_license.items())),
        "by_source": {source_id: dict(statuses) for source_id, statuses in sorted(by_source.items())},
        "files": files,
    }


def write_audit(root: Path) -> Path:
    path = root / "data" / "reports" / "audit_summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(audit_processed(root), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def export_profile(root: Path, profile: str, force: bool = False) -> tuple[Path, int]:
    if profile not in PROFILE_STATUSES:
        known = ", ".join(sorted(PROFILE_STATUSES))
        raise ValueError(f"unknown export profile '{profile}'. Known profiles: {known}")

    output = root / "data" / "releases" / f"{profile}.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not force:
        raise FileExistsError(f"{output} already exists; pass --force to replace it")

    allowed = PROFILE_STATUSES[profile]
    count = 0
    with output.open("w", encoding="utf-8") as out:
        for path in sorted((root / "data" / "processed").glob("*.jsonl")):
            for row in _read_jsonl(path):
                if row.get("release_status") not in allowed:
                    continue
                out.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
                out.write("\n")
                count += 1
    return output, count


def _read_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)
