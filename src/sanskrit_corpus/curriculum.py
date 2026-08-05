from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from .manifest import file_stats, utc_now
from .quality import QUALITY_SCHEMA

compute: Any = pc


@dataclass(frozen=True)
class CurriculumProfile:
    name: str
    phase: int | None
    description: str
    predicate: Callable[[pa.Table], pa.Array]


def _grammar_candidates(table: pa.Table) -> pa.Array:
    return compute.and_(
        compute.and_(
            compute.equal(table["provenance_class"], "human_source_verified"),
            compute.equal(table["curriculum_tier"], "general_clean"),
        ),
        compute.and_(
            compute.greater_equal(table["quality_score"], 0.95),
            compute.equal(compute.list_value_length(table["quality_flags"]), 0),
        ),
    )


def _phase_2_verified(table: pa.Table) -> pa.Array:
    return compute.and_(compute.equal(table["curriculum_tier"], "general_clean"), compute.invert(_grammar_candidates(table)))


def _tier(name: str) -> Callable[[pa.Table], pa.Array]:
    return lambda table: compute.equal(table["curriculum_tier"], name)


CURRICULUM_PROFILES = (
    CurriculumProfile(
        "phase_1_grammar_candidates",
        1,
        "Flag-free, high-scoring verified human-source text; candidates only, pending linguistic verification.",
        _grammar_candidates,
    ),
    CurriculumProfile("phase_2_verified_clean", 2, "Remaining structurally clean verified human-source text.", _phase_2_verified),
    CurriculumProfile("phase_3_ocr_recoverable", 3, "Human-source text requiring OCR repair or review.", _tier("ocr_recoverable")),
    CurriculumProfile("phase_4_synthetic", 4, "Deduplicated synthetic Sanskrit translations.", _tier("synthetic_translation")),
    CurriculumProfile("excluded_quarantine", None, "Low-quality records excluded pending manual review.", _tier("quarantine")),
    CurriculumProfile(
        "excluded_duplicates",
        None,
        "Exact duplicates excluded in favor of their higher-priority record.",
        _tier("exact_duplicate"),
    ),
)


def build_curriculum_manifests(root: Path, force: bool = False) -> Path:
    quality_dir = root / "data" / "quality"
    inputs = sorted(quality_dir.glob("sangraha_*.parquet"))
    if not inputs:
        raise FileNotFoundError(f"no quality sidecars found in {quality_dir}; run the quality command first")

    output_dir = root / "data" / "curriculum"
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {profile.name: output_dir / f"{profile.name}.parquet" for profile in CURRICULUM_PROFILES}
    existing = [path for path in outputs.values() if path.exists()]
    if existing and not force:
        raise FileExistsError(f"{existing[0]} already exists; pass --force to replace curriculum manifests")

    temporary = {name: path.with_name(f".{path.name}.{uuid4().hex}.tmp") for name, path in outputs.items()}
    writers = {name: pq.ParquetWriter(path, QUALITY_SCHEMA, compression="zstd") for name, path in temporary.items()}
    counts: Counter[str] = Counter()
    try:
        for input_path in inputs:
            parquet = pq.ParquetFile(input_path)
            if not QUALITY_SCHEMA.equals(parquet.schema_arrow, check_metadata=False):
                raise ValueError(f"quality sidecar schema mismatch: {input_path}")
            for batch in parquet.iter_batches(batch_size=8192):
                table = pa.Table.from_batches([batch], schema=QUALITY_SCHEMA)
                for profile in CURRICULUM_PROFILES:
                    selected = table.filter(profile.predicate(table))
                    if selected.num_rows:
                        writers[profile.name].write_table(selected)
                        counts[profile.name] += selected.num_rows
        for writer in writers.values():
            writer.close()
        writers.clear()
        for name, path in temporary.items():
            path.replace(outputs[name])
    except Exception:
        for writer in writers.values():
            writer.close()
        for path in temporary.values():
            path.unlink(missing_ok=True)
        raise

    profiles: list[dict[str, Any]] = []
    for profile in CURRICULUM_PROFILES:
        byte_count, checksum = file_stats(outputs[profile.name])
        profiles.append(
            {
                "name": profile.name,
                "phase": profile.phase,
                "description": profile.description,
                "record_count": counts[profile.name],
                "path": str(outputs[profile.name].relative_to(root)),
                "byte_count": byte_count,
                "checksum_sha256": checksum,
            }
        )
    manifest = {
        "created_at": utc_now(),
        "grammar_verification_status": "candidate_only",
        "quality_inputs": [str(path.relative_to(root)) for path in inputs],
        "profiles": profiles,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_temporary = manifest_path.with_name(f".{manifest_path.name}.{uuid4().hex}.tmp")
    manifest_temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    manifest_temporary.replace(manifest_path)
    return manifest_path
