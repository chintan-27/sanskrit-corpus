from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LicenseDecision:
    license_label: str
    release_status: str
    evidence_url: str | None = None
    attribution: str | None = None
    verified_at: str | None = None


@lru_cache(maxsize=1)
def load_license_policy() -> dict[str, Any]:
    resource = files("sanskrit_corpus").joinpath("license_policy.json")
    return json.loads(resource.read_text(encoding="utf-8"))


def resolve_license(root: Path, row: dict[str, Any]) -> LicenseDecision:
    source_id = str(row.get("source_id") or "")
    policy = load_license_policy().get("sources", {}).get(source_id)
    if not policy:
        return LicenseDecision(str(row.get("license_label", "missing")), str(row.get("release_status", "missing")))

    if policy.get("evidence_extractor") == "tei_license":
        extracted = _sarit_license(root, str(row.get("source_path") or ""))
        if extracted is not None:
            return LicenseDecision(
                extracted,
                "releasable",
                policy.get("evidence_url"),
                policy.get("attribution"),
                policy.get("verified_at"),
            )

    return LicenseDecision(
        policy["license_label"],
        policy["release_status"],
        policy.get("evidence_url"),
        policy.get("attribution"),
        policy.get("verified_at"),
    )


def apply_license(root: Path, row: dict[str, Any]) -> dict[str, Any]:
    decision = resolve_license(root, row)
    updated = dict(row)
    updated["license_label"] = decision.license_label
    updated["release_status"] = decision.release_status
    return updated


@lru_cache(maxsize=512)
def _read_tei_license(path_string: str) -> str | None:
    path = Path(path_string)
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return None
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] not in {"licence", "ref"}:
            continue
        target = str(element.attrib.get("target") or "").lower()
        text = " ".join(element.itertext()).lower()
        value = f"{target} {text}"
        if "by-sa/4.0" in value or "attribution-sharealike 4.0" in value:
            return "CC-BY-SA-4.0"
        if "by-sa/3.0" in value or "attribution-sharealike 3.0" in value:
            return "CC-BY-SA-3.0"
    return None


def _sarit_license(root: Path, source_path: str) -> str | None:
    if not source_path or Path(source_path).name != source_path:
        return None
    path = root / "data" / "raw" / "sarit_corpus" / source_path
    return _read_tei_license(str(path.resolve()))
