from __future__ import annotations

import csv
from pathlib import Path
from urllib.parse import urlsplit

from .config import DEFAULT_SEED_PATH
from .models import SourceCandidate


def _normalize_url(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    return raw.rstrip("/")


def _extract_root_domain(value: str) -> str:
    parsed = urlsplit(value)
    host = (parsed.netloc or parsed.path).lower().strip()
    if host.startswith("www."):
        host = host[4:]
    if ":" in host:
        host = host.split(":", 1)[0]
    return host


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def row_to_candidate(row: dict[str, str]) -> SourceCandidate:
    website = _normalize_url(row.get("website", ""))
    aanbod_url = _normalize_url(row.get("koopaanbod_url") or row.get("aanbod_url", ""))
    root_domain = (row.get("root_domain") or "").strip() or _extract_root_domain(website or aanbod_url)
    quality = (row.get("koopaanbod_url_quality") or row.get("aanbod_url_quality") or "missing").strip() or "missing"
    confidence_raw = (row.get("confidence") or "0").strip()

    return SourceCandidate(
        office_name=(row.get("office_name") or "").strip(),
        website=website,
        root_domain=root_domain,
        raw_place=(row.get("raw_place") or row.get("plaats") or "").strip(),
        normalized_place=(row.get("normalized_place") or row.get("gemeente") or "").strip(),
        gemeente=(row.get("gemeente") or "").strip(),
        plaats=(row.get("plaats") or "").strip(),
        place_status=(row.get("place_status") or "").strip(),
        place_review_reason=(row.get("place_review_reason") or "").strip(),
        provincie=(row.get("provincie") or "").strip(),
        aanbod_url=aanbod_url,
        aanbod_url_quality=quality,
        confidence=float(confidence_raw or 0),
        needs_review=(row.get("needs_review") or "").strip().lower() == "true",
        source_adapter="seed",
        source_origin="seed",
        review_reason=(row.get("review_reason") or "").strip(),
    )


def load_seed_candidates(path: Path = DEFAULT_SEED_PATH) -> list[SourceCandidate]:
    return [row_to_candidate(row) for row in _read_csv_rows(path)]
