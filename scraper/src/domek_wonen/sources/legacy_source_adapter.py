from __future__ import annotations

import csv
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from .access_policy import evaluate_source_access, summarize_access_decisions
from .delivery_fingerprint import fingerprint_sources, summarize_delivery_fingerprints
from .source_intelligence_loader import build_source_intelligence_record
from .source_intelligence_models import SourceIntelligenceRecord, normalize_key, normalize_text
from .source_intelligence_report import build_source_intelligence_report


LEGACY_FIELD_MAP = {
    "domain": "source_domain",
    "root_domain": "source_domain",
    "source_domain": "source_domain",
    "office_name": "source_name",
    "makelaar_name": "source_name",
    "source_name": "source_name",
    "website": "homepage_url",
    "homepage_url": "homepage_url",
    "website_url": "homepage_url",
    "aanbod_url": "aanbod_url",
    "koopaanbod_url": "aanbod_url",
    "aanbod_url_quality": "aanbod_url_status",
    "source_status": "aanbod_url_status",
    "legal_status": "access_status",
    "detected_platform": "detected_platform",
    "platform": "detected_platform",
    "source_quality_reason": "evidence",
    "evidence": "evidence",
    "source_origin": "notes",
    "notes": "notes",
}

PASSTHROUGH_FIELDS = {
    "source_id",
    "province",
    "gemeente",
    "city",
    "has_login",
    "has_captcha",
    "has_403",
    "has_sitemap",
    "has_wp_json",
    "has_json_ld",
    "has_visible_cards",
    "has_iframe",
    "iframe_domain",
    "is_funda_dependent",
    "is_pararius_dependent",
    "technology_signals",
    "delivery_mode",
    "delivery_mode_confidence",
    "parser_family_candidate",
    "estimated_listing_count",
    "koop_signal",
    "huur_signal",
    "commercial_signal",
    "project_signal",
    "recommended_action",
}


def load_legacy_source_records(path: Path | str) -> list[SourceIntelligenceRecord]:
    csv_path = Path(path)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [build_source_intelligence_record(_normalize_legacy_row(row)) for row in csv.DictReader(handle)]


def build_legacy_source_intelligence_report(path: Path | str) -> dict[str, object]:
    csv_path = Path(path)
    records = load_legacy_source_records(csv_path)
    source_report = build_source_intelligence_report(records)
    access_decisions = evaluate_source_access(records)
    fingerprint_results = fingerprint_sources(records)

    access_by_source_id = {decision.source_id: decision for decision in access_decisions}
    top_parser_family_candidates = _top_counts(
        result.parser_family_candidate
        for result in fingerprint_results
        if result.parser_family_candidate and result.can_proceed_to_parser_family
    )
    manual_review_queue = [
        asdict(result)
        for result in fingerprint_results
        if result.recommended_action in {"manual_review_needed", "legal_review"}
        or result.delivery_mode == "unknown_manual_review"
    ]
    blocked_sources = [
        asdict(decision) for decision in access_decisions if decision.access_status == "blocked"
    ]
    permission_required_sources = [
        asdict(decision)
        for decision in access_decisions
        if decision.access_status == "permission_required"
    ]
    production_parser_ready_sources = [
        asdict(result)
        for result in fingerprint_results
        if access_by_source_id[result.source_id].can_run_production_extraction
        and result.can_proceed_to_parser_family
        and bool(result.parser_family_candidate)
    ]

    return {
        "input_path": str(csv_path),
        "total_sources": len(records),
        "unique_domains": len({record.source_domain for record in records if record.source_domain}),
        "source_intelligence": source_report,
        "access_policy": summarize_access_decisions(access_decisions),
        "delivery_fingerprint": summarize_delivery_fingerprints(fingerprint_results),
        "top_parser_family_candidates": top_parser_family_candidates,
        "manual_review_queue": manual_review_queue,
        "blocked_sources": blocked_sources,
        "permission_required_sources": permission_required_sources,
        "production_parser_ready_sources": production_parser_ready_sources,
    }


def _normalize_legacy_row(row: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    evidence_parts: list[str] = []
    notes_parts: list[str] = []

    for raw_key, raw_value in row.items():
        key = normalize_key(raw_key)
        value = normalize_text(raw_value)
        if not value:
            continue

        target = LEGACY_FIELD_MAP.get(key)
        if target == "evidence":
            evidence_parts.append(value)
        elif target == "notes":
            notes_parts.append(value)
        elif target:
            normalized.setdefault(target, value)
        elif key in PASSTHROUGH_FIELDS:
            normalized.setdefault(key, value)

    if "city" in row and "gemeente" not in normalized:
        normalized["gemeente"] = normalize_text(row.get("city"))

    if evidence_parts:
        normalized["evidence"] = "; ".join(evidence_parts)
    if notes_parts:
        normalized["notes"] = "; ".join(notes_parts)

    _normalize_legacy_statuses(normalized)
    _infer_flags_from_legacy_text(normalized)
    return normalized


def _normalize_legacy_statuses(row: dict[str, str]) -> None:
    aanbod_status = normalize_key(row.get("aanbod_url_status"))
    if aanbod_status in {"valid", "ok", "clean", "available"}:
        row["aanbod_url_status"] = "valid"
    elif aanbod_status in {"suspect", "needs_review", "manual_review", "uncertain"}:
        row["aanbod_url_status"] = "suspect"
    elif aanbod_status in {"missing", "no_aanbod_url", "missing_website", "none"}:
        row["aanbod_url_status"] = "missing"

    access_status = normalize_key(row.get("access_status"))
    access_map = {
        "allowed": "allowed",
        "limited": "limited",
        "permission_required": "permission_required",
        "requires_permission": "permission_required",
        "legal_review": "legal_review",
        "blocked": "blocked",
        "disabled": "disabled",
        "unknown": "unknown",
        "researching": "researching",
    }
    if access_status in access_map:
        row["access_status"] = access_map[access_status]


def _infer_flags_from_legacy_text(row: dict[str, str]) -> None:
    text = normalize_key(
        " ".join(
            [
                row.get("source_domain", ""),
                row.get("homepage_url", ""),
                row.get("aanbod_url", ""),
                row.get("detected_platform", ""),
                row.get("evidence", ""),
                row.get("notes", ""),
            ]
        )
    )

    if "funda" in text:
        row["is_funda_dependent"] = "true"
    if "pararius" in text:
        row["is_pararius_dependent"] = "true"
    if "captcha" in text:
        row["has_captcha"] = "true"
    if "login" in text:
        row["has_login"] = "true"
    if "403" in text:
        row["has_403"] = "true"
    if "wp-json" in text:
        row["has_wp_json"] = "true"
    if "json-ld" in text or "json_ld" in text:
        row["has_json_ld"] = "true"
    if "visible cards" in text or "static cards" in text or "html cards" in text:
        row["has_visible_cards"] = "true"


def _top_counts(values: Iterable[str]) -> list[dict[str, object]]:
    counter = Counter(values)
    return [
        {"parser_family_candidate": key, "source_count": count}
        for key, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]
