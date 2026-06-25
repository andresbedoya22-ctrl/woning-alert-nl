from __future__ import annotations

import csv
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .realworks_capture_pilot import CapturePilotSource


REALWORKS_PUBLIC = "realworks_public"
ALLOWED_SELECTION_ACCESS_STATUSES = {"allowed", "limited"}
BLOCKING_ACCESS_STATUSES = {"blocked", "permission_required", "legal_review", "disabled"}
BLOCKING_TEXT_MARKERS = ("captcha", "login", "login_required", "login wall", "inloggen", "403", "forbidden")

LISTING_URL_KEYS = ("listing_url", "aanbod_url", "source_url")
SOURCE_DOMAIN_KEYS = ("source_domain", "root_domain", "domain", "website_domain")
PARSER_FAMILY_KEYS = ("parser_family_candidate", "parser_family", "detected_parser_family")
DELIVERY_MODE_KEYS = ("delivery_mode", "detected_delivery_mode", "detected_delivery_mode_enriched")
ACCESS_STATUS_KEYS = ("access_status", "legal_status")
CONFIDENCE_KEYS = ("confidence", "confidence_score", "score", "platform_confidence")
PRIORITY_SCORE_KEYS = ("priority_score", "score")


@dataclass(frozen=True, slots=True)
class SourceSelectionCandidate:
    source_id: str
    source_domain: str
    listing_url: str
    parser_family_candidate: str
    delivery_mode: str
    access_status: str
    confidence: float = 0.0
    priority_score: int = 0
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SourceSelectionResult:
    selected_sources: tuple[CapturePilotSource, ...]
    candidates_considered: int
    candidates_selected: int
    rejected_count: int
    rejection_reasons: dict[str, int]
    warnings: tuple[str, ...] = ()


def select_realworks_pilot_sources_from_report(
    report: Mapping[str, Any],
    max_sources: int = 5,
) -> SourceSelectionResult:
    if max_sources <= 0:
        return SourceSelectionResult(
            selected_sources=(),
            candidates_considered=0,
            candidates_selected=0,
            rejected_count=0,
            rejection_reasons={},
            warnings=("max_sources_must_be_positive",),
        )

    rows, row_warnings = _candidate_rows_from_report(report)
    source_master_index, index_warnings = _source_master_index_from_report(report)
    accepted: list[SourceSelectionCandidate] = []
    rejection_reasons: Counter[str] = Counter()

    for raw_row in rows:
        row = _with_source_master_url(raw_row, source_master_index)
        candidate = candidate_from_report_row(row)
        reasons = _rejection_reasons(row, candidate)
        if reasons:
            rejection_reasons.update(reasons)
            continue
        if candidate is not None:
            accepted.append(candidate)

    accepted.sort(key=_candidate_sort_key)
    selected = tuple(candidate_to_capture_pilot_source(candidate) for candidate in accepted[:max_sources])
    return SourceSelectionResult(
        selected_sources=selected,
        candidates_considered=len(rows),
        candidates_selected=len(selected),
        rejected_count=len(rows) - len(accepted),
        rejection_reasons=dict(sorted(rejection_reasons.items())),
        warnings=_dedupe((*row_warnings, *index_warnings)),
    )


def candidate_from_report_row(row: Mapping[str, Any]) -> SourceSelectionCandidate | None:
    normalized = _normalize_row(row)
    if not normalized:
        return None

    source_id = _first_value(normalized, ("source_id", "id")) or _source_id_from_domain(normalized)
    source_domain = _normalize_domain(_first_value(normalized, SOURCE_DOMAIN_KEYS))
    listing_url = _clean_text(_first_value(normalized, LISTING_URL_KEYS))
    parser_family_candidate = _normalize_key(_first_value(normalized, PARSER_FAMILY_KEYS))
    delivery_mode = _normalize_key(_first_value(normalized, DELIVERY_MODE_KEYS))
    access_status = _canonical_access_status(_first_value(normalized, ACCESS_STATUS_KEYS))
    confidence = _float_value(_first_value(normalized, CONFIDENCE_KEYS))
    priority_score = _int_value(_first_value(normalized, PRIORITY_SCORE_KEYS))

    if not any((source_id, source_domain, listing_url, parser_family_candidate, delivery_mode, access_status)):
        return None

    return SourceSelectionCandidate(
        source_id=source_id,
        source_domain=source_domain,
        listing_url=listing_url,
        parser_family_candidate=parser_family_candidate,
        delivery_mode=delivery_mode,
        access_status=access_status,
        confidence=confidence,
        priority_score=priority_score,
        reasons=_candidate_reasons(normalized),
    )


def candidate_to_capture_pilot_source(candidate: SourceSelectionCandidate) -> CapturePilotSource:
    return CapturePilotSource(
        source_id=candidate.source_id,
        source_domain=candidate.source_domain,
        listing_url=candidate.listing_url,
        parser_family_candidate=candidate.parser_family_candidate,
        delivery_mode=candidate.delivery_mode,
    )


def _candidate_rows_from_report(report: Mapping[str, Any]) -> tuple[tuple[Mapping[str, Any], ...], tuple[str, ...]]:
    production_rows = report.get("production_parser_ready_sources")
    if isinstance(production_rows, list):
        return tuple(row for row in production_rows if isinstance(row, Mapping)), ()

    for key in (
        "enriched_sources",
        "sources",
        "records",
        "delivery_fingerprint_results",
        "fingerprint_results",
    ):
        rows = report.get(key)
        if isinstance(rows, list):
            return tuple(row for row in rows if isinstance(row, Mapping)), ("production_parser_ready_sources_missing",)

    for parent_key in ("source_intelligence", "delivery_fingerprint"):
        parent = report.get(parent_key)
        if not isinstance(parent, Mapping):
            continue
        for key in ("production_parser_ready_sources", "sources", "records", "results"):
            rows = parent.get(key)
            if isinstance(rows, list):
                return tuple(row for row in rows if isinstance(row, Mapping)), (
                    "production_parser_ready_sources_missing",
                )

    return (), ("production_parser_ready_sources_missing", "no_candidate_rows")


def _source_master_index_from_report(report: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], tuple[str, ...]]:
    path_value = report.get("input_source_master_path") or report.get("input_path") or report.get("source_master_path")
    if not isinstance(path_value, str) or not path_value.strip():
        return {}, ()

    path = Path(path_value)
    if not path.exists():
        return {}, ("source_master_path_not_found",)

    index: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            normalized = _normalize_row(row)
            indexed = {
                "listing_url": _first_value(normalized, LISTING_URL_KEYS),
                "aanbod_url": _first_value(normalized, LISTING_URL_KEYS),
                "source_domain": _normalize_domain(_first_value(normalized, SOURCE_DOMAIN_KEYS)),
                "priority_score": _first_value(normalized, PRIORITY_SCORE_KEYS),
                "confidence": _first_value(normalized, CONFIDENCE_KEYS),
            }
            for key in (_clean_text(normalized.get("source_id")), indexed["source_domain"]):
                if key:
                    index.setdefault(key, indexed)
    return index, ()


def _with_source_master_url(
    row: Mapping[str, Any],
    source_master_index: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any]:
    if not source_master_index:
        return row
    normalized = _normalize_row(row)
    if _first_value(normalized, LISTING_URL_KEYS):
        return row

    source_id = _clean_text(normalized.get("source_id"))
    source_domain = _normalize_domain(_first_value(normalized, SOURCE_DOMAIN_KEYS))
    source_master_row = source_master_index.get(source_id) or source_master_index.get(source_domain)
    if not source_master_row:
        return row

    merged = dict(row)
    for key in ("listing_url", "aanbod_url", "priority_score", "confidence"):
        if not _clean_text(merged.get(key)) and _clean_text(source_master_row.get(key)):
            merged[key] = source_master_row[key]
    if not _first_value(_normalize_row(merged), SOURCE_DOMAIN_KEYS) and source_master_row.get("source_domain"):
        merged["source_domain"] = source_master_row["source_domain"]
    return merged


def _rejection_reasons(
    row: Mapping[str, Any],
    candidate: SourceSelectionCandidate | None,
) -> tuple[str, ...]:
    normalized = _normalize_row(row)
    if candidate is None:
        return ("missing_source_domain",)

    reasons: list[str] = []
    if candidate.parser_family_candidate != REALWORKS_PUBLIC or candidate.delivery_mode != REALWORKS_PUBLIC:
        reasons.append("not_realworks_public")
    if candidate.access_status not in ALLOWED_SELECTION_ACCESS_STATUSES:
        if candidate.access_status in BLOCKING_ACCESS_STATUSES or _has_blocked_or_permission_signal(normalized):
            reasons.append("blocked_or_permission_required")
        else:
            reasons.append("not_allowed_access")
    if not candidate.listing_url:
        reasons.append("missing_listing_url")
    if not candidate.source_domain:
        reasons.append("missing_source_domain")
    if _has_funda_dependency(normalized, candidate):
        reasons.append("funda_dependency")
    if _has_pararius_dependency(normalized, candidate):
        reasons.append("pararius_dependency")
    if _has_blocked_or_permission_signal(normalized):
        reasons.append("blocked_or_permission_required")
    if _requires_manual_review(normalized, candidate):
        reasons.append("manual_review_required")
    return _dedupe(reasons)


def _candidate_sort_key(candidate: SourceSelectionCandidate) -> tuple[int, float, int, str]:
    access_rank = 0 if candidate.access_status == "allowed" else 1
    return (access_rank, -candidate.confidence, -candidate.priority_score, candidate.source_domain)


def _candidate_reasons(row: Mapping[str, str]) -> tuple[str, ...]:
    reason_values = (
        _first_value(row, ("reason", "recommended_action")),
        _first_value(row, ("evidence_signals", "evidence", "notes")),
    )
    return _dedupe(value for value in reason_values if value)


def _requires_manual_review(row: Mapping[str, Any], candidate: SourceSelectionCandidate) -> bool:
    if candidate.delivery_mode == "unknown_manual_review":
        return True
    if _normalize_key(row.get("recommended_action")) in {"manual_review_needed", "manual_review", "legal_review"}:
        return True
    if _bool_value(row.get("needs_review")):
        return True
    if _normalize_key(row.get("can_proceed_to_parser_family")) == "false":
        return True
    text = _joined_row_text(row)
    return "manual_review" in text or "unknown_manual_review" in text


def _has_funda_dependency(row: Mapping[str, Any], candidate: SourceSelectionCandidate) -> bool:
    if _bool_value(row.get("is_funda_dependent")):
        return True
    text = " ".join((candidate.source_domain, candidate.listing_url, _joined_row_text(row)))
    return "funda.nl" in text or "funda_dependency" in text or "funda_iframe_blocked" in text


def _has_pararius_dependency(row: Mapping[str, Any], candidate: SourceSelectionCandidate) -> bool:
    if _bool_value(row.get("is_pararius_dependent")):
        return True
    text = " ".join((candidate.source_domain, candidate.listing_url, _joined_row_text(row)))
    return "pararius.nl" in text or "pararius_dependency" in text or "pararius_external_blocked" in text


def _has_blocked_or_permission_signal(row: Mapping[str, Any]) -> bool:
    if any(_bool_value(row.get(key)) for key in ("has_captcha", "has_login", "has_403")):
        return True
    if _normalize_key(row.get("access_status")) in BLOCKING_ACCESS_STATUSES:
        return True
    if _normalize_key(row.get("required_action")) in {"do_not_use", "request_permission", "legal_review"}:
        return True
    text = _joined_row_text(row)
    return any(marker in text for marker in BLOCKING_TEXT_MARKERS)


def _normalize_row(row: Mapping[str, Any]) -> dict[str, str]:
    return {_normalize_key(key): _clean_text(value) for key, value in row.items()}


def _first_value(row: Mapping[str, str], keys: Iterable[str]) -> str:
    for key in keys:
        value = _clean_text(row.get(key))
        if value:
            return value
    return ""


def _canonical_access_status(value: object) -> str:
    key = _normalize_key(value)
    return {
        "allowed_official_source": "allowed",
        "requires_permission": "permission_required",
        "needs_permission": "permission_required",
        "manual_review": "researching",
    }.get(key, key)


def _source_id_from_domain(row: Mapping[str, str]) -> str:
    domain = _normalize_domain(_first_value(row, SOURCE_DOMAIN_KEYS))
    return domain


def _normalize_domain(value: object) -> str:
    text = _clean_text(value).lower()
    if not text:
        return ""
    candidate = text if "://" in text else f"https://{text}"
    parts = urlsplit(candidate)
    host = (parts.netloc or parts.path).split("/", 1)[0].split(":", 1)[0].strip().lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return " ".join(_clean_text(item) for item in value if _clean_text(item))
    return str(value).strip()


def _normalize_key(value: object) -> str:
    return _clean_text(value).strip().lower().replace("-", "_").replace(" ", "_")


def _float_value(value: object) -> float:
    try:
        parsed = float(_clean_text(value) or "0")
    except ValueError:
        return 0.0
    if parsed > 1.0:
        return min(parsed / 100.0, 1.0)
    return max(parsed, 0.0)


def _int_value(value: object) -> int:
    try:
        return int(float(_clean_text(value) or "0"))
    except ValueError:
        return 0


def _bool_value(value: object) -> bool:
    return _normalize_key(value) in {"1", "true", "yes", "y", "ja"}


def _joined_row_text(row: Mapping[str, Any]) -> str:
    values = (
        row.get("blocking_signals"),
        row.get("risk_flags"),
        row.get("reason"),
        row.get("required_action"),
        row.get("recommended_action"),
        row.get("notes"),
        row.get("evidence"),
        row.get("technology_signals"),
        row.get("delivery_mode"),
        row.get("parser_family_candidate"),
        row.get("listing_url"),
        row.get("aanbod_url"),
        row.get("source_url"),
    )
    return _normalize_key(" ".join(_clean_text(value) for value in values if _clean_text(value)))


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)
