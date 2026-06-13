from __future__ import annotations

import csv
from pathlib import Path

from .models import SourceCandidate


def _bool_str(value: bool) -> str:
    return "true" if value else "false"


def _source_id(candidate: SourceCandidate) -> str:
    domain = (candidate.root_domain or "unknown-domain").lower()
    gemeente = (candidate.gemeente or "unknown-gemeente").lower().replace(" ", "-")
    return f"{domain}__{gemeente}"


def _legal_status(candidate: SourceCandidate) -> str:
    if candidate.source_origin == "aggregator_fallback":
        return "disabled_legal_review"
    if candidate.aanbod_url_quality == "valid":
        return "allowed_official_source"
    if candidate.website_resolution_status == "needs_manual_review":
        return "missing_website"
    if candidate.aanbod_url_quality == "suspect":
        return "needs_manual_review"
    if candidate.aanbod_url_quality == "missing":
        return "missing"
    return "rejected"


def build_source_master_rows(candidates: list[SourceCandidate], *, run_timestamp: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for candidate in candidates:
        legal_status = _legal_status(candidate)
        is_active = legal_status == "allowed_official_source"
        needs_review = candidate.needs_review or candidate.aanbod_url_quality == "suspect" or legal_status in {
            "needs_manual_review",
            "missing_website",
        }
        last_audited_at = run_timestamp if candidate.aanbod_detection_method == "browser_audit" else ""
        rows.append(
            {
                "source_id": _source_id(candidate),
                "office_name": candidate.office_name,
                "root_domain": candidate.root_domain,
                "website": candidate.website,
                "gemeente": candidate.gemeente,
                "province": candidate.provincie,
                "source_origin": candidate.source_origin,
                "aanbod_url": candidate.aanbod_url,
                "aanbod_url_quality": candidate.aanbod_url_quality,
                "confidence_score": str(candidate.aanbod_detection_score or candidate.score),
                "needs_review": _bool_str(needs_review),
                "review_reason": candidate.review_reason or candidate.aanbod_validation_reason,
                "legal_status": legal_status,
                "last_seen_at": run_timestamp,
                "last_audited_at": last_audited_at,
                "is_active": _bool_str(is_active),
            }
        )
    return rows


def write_source_master(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_id",
                "office_name",
                "root_domain",
                "website",
                "gemeente",
                "province",
                "source_origin",
                "aanbod_url",
                "aanbod_url_quality",
                "confidence_score",
                "needs_review",
                "review_reason",
                "legal_status",
                "last_seen_at",
                "last_audited_at",
                "is_active",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
