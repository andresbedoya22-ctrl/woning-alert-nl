from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from .models import SourceCandidate


SOURCE_MASTER_FIELDNAMES = [
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
    "score",
    "needs_review",
    "review_reason",
    "legal_status",
    "last_seen_at",
    "last_audited_at",
    "run_id",
    "is_active",
]


def _bool_str(value: bool) -> str:
    return "true" if value else "false"


def _source_id(candidate: SourceCandidate) -> str:
    domain = (candidate.root_domain or "unknown-domain").lower()
    gemeente = (candidate.gemeente or "unknown-gemeente").lower().replace(" ", "-")
    return f"{domain}__{gemeente}"


def _legal_status(candidate: SourceCandidate) -> str:
    if candidate.source_origin == "aggregator_fallback":
        return "disabled_legal_review"
    if candidate.rejection_reason == "missing_website" or candidate.website_resolution_status == "needs_manual_review":
        return "missing_website"
    if candidate.aanbod_url_quality == "valid":
        return "allowed_official_source"
    if candidate.aanbod_url_quality == "suspect":
        return "needs_manual_review"
    if candidate.aanbod_url_quality == "missing":
        return "missing"
    return "rejected"


def _normalize_bool(value: str | bool | None, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    normalized = (value or "").strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    return default


def _parse_int(value: object, *, default: int = 0) -> int:
    try:
        return int(str(value or "").strip())
    except (TypeError, ValueError):
        return default


def _read_first(row: dict[str, str], *keys: str, default: str = "") -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _source_id_from_row(row: dict[str, str]) -> str:
    existing = _read_first(row, "source_id")
    if existing:
        return existing
    domain = _read_first(row, "root_domain", default="unknown-domain").lower()
    gemeente = _read_first(row, "gemeente", default="unknown-gemeente").lower().replace(" ", "-")
    return f"{domain}__{gemeente}"


def _legal_status_from_row(row: dict[str, str], *, aanbod_url_quality: str, source_origin: str) -> str:
    existing = _read_first(row, "legal_status")
    if existing:
        return existing
    if source_origin == "aggregator_fallback":
        return "disabled_legal_review"
    if aanbod_url_quality == "valid":
        return "allowed_official_source"
    if aanbod_url_quality == "suspect":
        return "needs_manual_review"
    if aanbod_url_quality == "missing":
        return "missing"
    return "rejected"


def _needs_review_from_row(row: dict[str, str], *, aanbod_url_quality: str, score: int, legal_status: str) -> bool:
    if "needs_review" in row and str(row.get("needs_review") or "").strip():
        return _normalize_bool(row.get("needs_review"))
    return aanbod_url_quality != "valid" or legal_status in {"needs_manual_review", "missing_website"} or score < 70


def _build_master_row(
    *,
    source_id: str,
    office_name: str,
    root_domain: str,
    website: str,
    gemeente: str,
    province: str,
    source_origin: str,
    aanbod_url: str,
    aanbod_url_quality: str,
    confidence_score: int,
    score: int,
    needs_review: bool,
    review_reason: str,
    legal_status: str,
    last_seen_at: str,
    last_audited_at: str,
    run_id: str,
) -> dict[str, str]:
    is_active = legal_status == "allowed_official_source"
    return {
        "source_id": source_id,
        "office_name": office_name,
        "root_domain": root_domain,
        "website": website,
        "gemeente": gemeente,
        "province": province,
        "source_origin": source_origin,
        "aanbod_url": aanbod_url,
        "aanbod_url_quality": aanbod_url_quality,
        "confidence_score": str(confidence_score),
        "score": str(score),
        "needs_review": _bool_str(needs_review),
        "review_reason": review_reason,
        "legal_status": legal_status,
        "last_seen_at": last_seen_at,
        "last_audited_at": last_audited_at,
        "run_id": run_id,
        "is_active": _bool_str(is_active),
    }


def build_source_master_rows(candidates: list[SourceCandidate], *, run_timestamp: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for candidate in candidates:
        legal_status = _legal_status(candidate)
        needs_review = candidate.needs_review or candidate.aanbod_url_quality == "suspect" or legal_status in {
            "needs_manual_review",
            "missing_website",
        }
        last_audited_at = run_timestamp if candidate.aanbod_detection_method == "browser_audit" else ""
        score = candidate.score
        confidence_score = candidate.aanbod_detection_score or score
        rows.append(
            _build_master_row(
                source_id=_source_id(candidate),
                office_name=candidate.office_name,
                root_domain=candidate.root_domain,
                website=candidate.website,
                gemeente=candidate.gemeente,
                province=candidate.provincie,
                source_origin=candidate.source_origin,
                aanbod_url=candidate.aanbod_url,
                aanbod_url_quality=candidate.aanbod_url_quality,
                confidence_score=confidence_score,
                score=score,
                needs_review=needs_review,
                review_reason=candidate.review_reason or candidate.aanbod_validation_reason,
                legal_status=legal_status,
                last_seen_at=run_timestamp,
                last_audited_at=last_audited_at,
                run_id=run_timestamp,
            )
        )
    return rows


def build_source_master_rows_from_discovered_rows(
    rows: Iterable[dict[str, str]],
    *,
    run_timestamp: str,
    default_run_id: str | None = None,
) -> list[dict[str, str]]:
    master_rows: list[dict[str, str]] = []
    fallback_run_id = default_run_id or run_timestamp or "latest"
    for row in rows:
        aanbod_url_quality = _read_first(row, "aanbod_url_quality", default="missing")
        source_origin = _read_first(row, "source_origin", default="source_discovery")
        score = _parse_int(row.get("score"), default=_parse_int(row.get("candidate_score"), default=0))
        confidence_score = _parse_int(row.get("confidence_score"), default=_parse_int(row.get("aanbod_detection_score"), default=score))
        legal_status = _legal_status_from_row(row, aanbod_url_quality=aanbod_url_quality, source_origin=source_origin)
        last_seen_at = _read_first(row, "last_seen_at", default=run_timestamp)
        run_id = _read_first(row, "run_id", default=fallback_run_id)
        needs_review = _needs_review_from_row(row, aanbod_url_quality=aanbod_url_quality, score=score, legal_status=legal_status)
        last_audited_at = _read_first(row, "last_audited_at")
        if not last_audited_at and _read_first(row, "aanbod_detection_method") == "browser_audit":
            last_audited_at = run_timestamp
        master_rows.append(
            _build_master_row(
                source_id=_source_id_from_row(row),
                office_name=_read_first(row, "office_name"),
                root_domain=_read_first(row, "root_domain"),
                website=_read_first(row, "website"),
                gemeente=_read_first(row, "gemeente"),
                province=_read_first(row, "province", "provincie"),
                source_origin=source_origin,
                aanbod_url=_read_first(row, "aanbod_url"),
                aanbod_url_quality=aanbod_url_quality,
                confidence_score=confidence_score,
                score=score,
                needs_review=needs_review,
                review_reason=_read_first(row, "review_reason", "aanbod_validation_reason"),
                legal_status=legal_status,
                last_seen_at=last_seen_at,
                last_audited_at=last_audited_at,
                run_id=run_id,
            )
        )
    return master_rows


def build_source_master_from_csv(
    input_path: Path,
    *,
    run_timestamp: str,
    default_run_id: str | None = None,
) -> list[dict[str, str]]:
    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        discovered_rows = list(csv.DictReader(handle))
    return build_source_master_rows_from_discovered_rows(
        discovered_rows,
        run_timestamp=run_timestamp,
        default_run_id=default_run_id,
    )


def write_source_master(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SOURCE_MASTER_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
