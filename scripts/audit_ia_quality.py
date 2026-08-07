#!/usr/bin/env python3
"""Sample compacted Internet Archive OCR and report basic text-quality signals."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any


def percentile(values: list[float | int], fraction: float) -> float | int:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * fraction))]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--sample", type=int, default=1000)
    parser.add_argument("--max-chars", type=int, default=2_000_000)
    parser.add_argument("--glob", default="*/*.txt.gz")
    args = parser.parse_args()
    paths = list((args.root / "data/raw/internet_archive").glob(args.glob))
    selected = random.Random(20260807).sample(paths, min(args.sample, len(paths)))
    rows: list[dict[str, Any]] = []
    for path in selected:
        try:
            with gzip.open(path, "rt", encoding="utf-8", errors="replace") as source:
                text = source.read(args.max_chars)
        except (OSError, EOFError):
            continue
        letters = [character for character in text if character.isalpha()]
        devanagari = sum("\u0900" <= character <= "\u097f" for character in letters)
        latin = sum("a" <= character.lower() <= "z" for character in letters)
        metadata: dict[str, Any] = {}
        metadata_path = path.parent / "_metadata.json"
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
        archive_metadata = metadata.get("metadata", metadata)
        rows.append(
            {
                "path": str(path),
                "excerpt": re.sub(r"\s+", " ", text).strip()[:500],
                "characters": len(text),
                "devanagari_ratio": devanagari / len(letters) if letters else 0.0,
                "latin_ratio": latin / len(letters) if letters else 0.0,
                "weird": text.count("\ufffd") + text.count("\x00"),
                "digest": hashlib.sha256(text.encode()).hexdigest(),
                "language": archive_metadata.get("language") if isinstance(archive_metadata, dict) else None,
            }
        )
    ratios = [row["devanagari_ratio"] for row in rows]
    latin_ratios = [row["latin_ratio"] for row in rows]
    lengths = [row["characters"] for row in rows]
    report = {
        "files_total": len(paths),
        "sample_files": len(rows),
        "devanagari_ratio": {
            "median": percentile(ratios, 0.5),
            "p10": percentile(ratios, 0.1),
            "p90": percentile(ratios, 0.9),
            "below_0.45": sum(value < 0.45 for value in ratios),
            "above_0.85": sum(value >= 0.85 for value in ratios),
        },
        "latin_ratio": {
            "median": percentile(latin_ratios, 0.5),
            "above_0.25": sum(value > 0.25 for value in latin_ratios),
            "above_0.50": sum(value > 0.50 for value in latin_ratios),
        },
        "characters_read": {
            "median": percentile(lengths, 0.5),
            "p10": percentile(lengths, 0.1),
            "p90": percentile(lengths, 0.9),
            "empty_or_tiny": sum(value < 100 for value in lengths),
        },
        "replacement_or_nul_files": sum(row["weird"] > 0 for row in rows),
        "exact_duplicate_prefixes": len(rows) - len({row["digest"] for row in rows}),
        "metadata_languages": Counter(str(row["language"]) for row in rows).most_common(15),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    selectors = {
        "HIGH_DEVANAGARI": lambda row: (row["devanagari_ratio"], row["characters"]),
        "HIGH_LATIN": lambda row: (row["latin_ratio"], row["characters"]),
        "LOW_DEVANAGARI": lambda row: (-row["devanagari_ratio"], row["characters"]),
        "CORRUPT": lambda row: (row["weird"], row["characters"]),
    }
    for label, selector in selectors.items():
        row = max(rows, key=selector)
        print(f"\n--- {label} {row['path']}")
        print(
            f"devanagari={row['devanagari_ratio']:.3f} latin={row['latin_ratio']:.3f} "
            f"weird={row['weird']} chars={row['characters']} language={row['language']}"
        )
        print(row["excerpt"])


if __name__ == "__main__":
    main()
