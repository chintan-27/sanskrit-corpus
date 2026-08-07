from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

QUERY = "sanskrit AND mediatype:texts"
FIELDS = ["identifier", "title", "format", "language", "date", "creator", "rights", "licenseurl", "collection"]
OCR_FORMATS = {"DjVuTXT", "Djvu XML", "OCR Search Text", "hOCR", "chOCR"}


def fetch_cursor(cursor: str | None, count: int, retries: int = 5) -> dict[str, Any]:
    params = urllib.parse.urlencode(
        {
            "q": QUERY,
            "fields": ",".join(FIELDS),
            "count": count,
            **({"cursor": cursor} if cursor else {}),
        },
    )
    request = urllib.request.Request(
        f"https://archive.org/services/search/v1/scrape?{params}",
        headers={"User-Agent": "sanskrit-corpus/0.1 (research metadata census)"},
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                payload = json.load(response)
            if isinstance(payload, dict):
                return payload
        except Exception:
            if attempt + 1 == retries:
                raise
            time.sleep(2**attempt)
    raise RuntimeError("unreachable")


def formats_for(item: dict[str, Any]) -> set[str]:
    value = item.get("format", [])
    if isinstance(value, str):
        return {value}
    return {str(entry) for entry in value} if isinstance(value, list) else set()


def classify(item: dict[str, Any]) -> dict[str, Any]:
    formats = formats_for(item)
    has_ocr = bool(formats & OCR_FORMATS)
    pdf_formats = {value for value in formats if "PDF" in value.upper()}
    usable_pdf_formats = {value for value in pdf_formats if "ENCRYPTED" not in value.upper()}
    return {
        **item,
        "has_ocr": has_ocr,
        "has_pdf": bool(pdf_formats),
        "has_usable_pdf": bool(usable_pdf_formats),
        "ocr_formats": sorted(formats & OCR_FORMATS),
        "pdf_formats": sorted(pdf_formats),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/manifests/internet_archive_format_census.jsonl"))
    parser.add_argument("--summary", type=Path, default=Path("data/reports/internet_archive_format_census.json"))
    parser.add_argument("--count", type=int, default=10000)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(f"{args.output.name}.partial")
    counts: Counter[str] = Counter()
    format_counts: Counter[str] = Counter()
    seen_identifiers: set[str] = set()

    with temporary.open("w", encoding="utf-8") as output:
        cursor: str | None = None
        total = 0
        while True:
            payload = fetch_cursor(cursor, args.count)
            if not total:
                total = int(payload.get("total", 0))
            raw_items = payload.get("items", [])
            if not isinstance(raw_items, list) or not raw_items:
                break
            for raw_item in raw_items:
                if not isinstance(raw_item, dict):
                    continue
                identifier = str(raw_item.get("identifier", ""))
                if not identifier or identifier in seen_identifiers:
                    counts["duplicate_or_missing_identifier"] += 1
                    continue
                seen_identifiers.add(identifier)
                item = classify(raw_item)
                output.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
                counts["items"] += 1
                for key in ("has_ocr", "has_pdf", "has_usable_pdf"):
                    counts[key] += bool(item[key])
                counts["ocr_and_usable_pdf"] += bool(item["has_ocr"] and item["has_usable_pdf"])
                counts["ocr_no_usable_pdf"] += bool(item["has_ocr"] and not item["has_usable_pdf"])
                counts["usable_pdf_no_ocr"] += bool(item["has_usable_pdf"] and not item["has_ocr"])
                counts["neither"] += bool(not item["has_ocr"] and not item["has_usable_pdf"])
                format_counts.update(formats_for(item))
            output.flush()
            print(f"retrieved={counts['items']} total={total}", flush=True)
            next_cursor = payload.get("cursor")
            if not isinstance(next_cursor, str) or not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor
    if counts["items"] < total:
        raise RuntimeError(f"incomplete census: retrieved {counts['items']} of {total} reported items")
    temporary.replace(args.output)
    summary = {
        "query": QUERY,
        "reported_items": total,
        "retrieved_items": counts["items"],
        "counts": dict(counts),
        "top_formats": format_counts.most_common(50),
        "output": str(args.output),
    }
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
