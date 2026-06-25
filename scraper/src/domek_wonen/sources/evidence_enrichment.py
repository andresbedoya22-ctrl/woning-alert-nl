from __future__ import annotations

import csv
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from .access_policy import evaluate_source_access, summarize_access_decisions
from .delivery_fingerprint import fingerprint_sources, summarize_delivery_fingerprints
from .legacy_source_adapter import load_legacy_source_records
from .source_intelligence_loader import apply_conservative_classification
from .source_intelligence_models import (
    SourceIntelligenceRecord,
    normalize_domain,
    normalize_key,
    normalize_text,
    parse_bool,
    parse_float,
)
from .source_intelligence_report import build_source_intelligence_report


DOMAIN_COLUMNS = (
    "source_domain",
    "root_domain",
    "domain",
    "website_domain",
    "homepage_url",
    "website",
    "website_url",
    "aanbod_url",
)

PLATFORM_COLUMNS = ("detected_platform", "platform", "platform_guess", "current_platform_guess")
DELIVERY_MODE_COLUMNS = (
    "delivery_mode",
    "detected_delivery_mode",
    "detected_delivery_mode_enriched",
    "current_delivery_mode",
)
PARSER_FAMILY_COLUMNS = ("parser_family_candidate",)
TECHNOLOGY_SIGNAL_COLUMNS = (
    "technology_signals",
    "signals",
    "detection_reasons",
    "fetch_status",
    "parser_status",
    "operational_status",
)
EVIDENCE_COLUMNS = ("evidence", "notes", "recommended_action", "recommended_next_action")
CONFIDENCE_COLUMNS = ("confidence_score", "confidence", "score", "platform_confidence")
BOOLEAN_COLUMNS = (
    "has_wp_json",
    "has_json_ld",
    "has_sitemap",
    "has_visible_cards",
    "has_iframe",
    "is_funda_dependent",
    "is_pararius_dependent",
    "has_captcha",
    "has_login",
    "has_403",
)

UNKNOWN_VALUES = {"", "unknown", "unknown_manual_review", "custom", "none", "null", "missing_input"}
BLOCKER_FIELDS = ("is_funda_dependent", "is_pararius_dependent", "has_captcha", "has_login", "has_403")


def load_platform_evidence(path: Path | str) -> dict[str, dict[str, Any]]:
    csv_path = Path(path)
    evidence_by_domain: dict[str, dict[str, Any]] = {}
    if not csv_path.exists():
        return evidence_by_domain

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            evidence = _normalize_evidence_row(row, csv_path)
            if not evidence["domains"]:
                continue
            for domain in evidence["domains"]:
                current = evidence_by_domain.get(domain)
                evidence_by_domain[domain] = _merge_evidence(current, evidence)
    return evidence_by_domain


def enrich_source_records_with_evidence(
    records: Iterable[SourceIntelligenceRecord],
    evidence_by_domain: Mapping[str, Mapping[str, Any]],
) -> list[SourceIntelligenceRecord]:
    enriched_records: list[SourceIntelligenceRecord] = []
    for record in records:
        evidence = _find_evidence_for_record(record, evidence_by_domain)
        if not evidence:
            enriched_records.append(SourceIntelligenceRecord(**asdict(record)))
            continue

        updated = SourceIntelligenceRecord(**asdict(record))
        _apply_evidence(updated, evidence)
        apply_conservative_classification(updated)
        enriched_records.append(updated)
    return enriched_records


def build_enriched_legacy_source_report(
    source_master_path: Path | str,
    evidence_paths: Iterable[Path | str],
) -> dict[str, object]:
    source_path = Path(source_master_path)
    evidence_path_list = [Path(path) for path in evidence_paths]
    records = load_legacy_source_records(source_path)
    raw_fingerprint_results = fingerprint_sources(records)

    evidence_by_domain: dict[str, dict[str, Any]] = {}
    for evidence_path in evidence_path_list:
        for domain, evidence in load_platform_evidence(evidence_path).items():
            evidence_by_domain[domain] = _merge_evidence(evidence_by_domain.get(domain), evidence)

    enriched_records = enrich_source_records_with_evidence(records, evidence_by_domain)
    source_report = build_source_intelligence_report(enriched_records)
    access_decisions = evaluate_source_access(enriched_records)
    fingerprint_results = fingerprint_sources(enriched_records)
    access_by_source_id = {decision.source_id: decision for decision in access_decisions}

    production_parser_ready_sources = [
        asdict(result)
        for result in fingerprint_results
        if access_by_source_id[result.source_id].can_run_production_extraction
        and result.can_proceed_to_parser_family
        and bool(result.parser_family_candidate)
    ]

    return {
        "input_source_master_path": str(source_path),
        "evidence_paths": [str(path) for path in evidence_path_list],
        "total_sources": len(enriched_records),
        "unique_domains": len({record.source_domain for record in enriched_records if record.source_domain}),
        "source_intelligence": source_report,
        "access_policy": summarize_access_decisions(access_decisions),
        "delivery_fingerprint": summarize_delivery_fingerprints(fingerprint_results),
        "top_parser_family_candidates": _top_counts(
            result.parser_family_candidate
            for result in fingerprint_results
            if result.parser_family_candidate and result.can_proceed_to_parser_family
        ),
        "manual_review_queue": [
            asdict(result)
            for result in fingerprint_results
            if result.recommended_action in {"manual_review_needed", "legal_review"}
            or result.delivery_mode == "unknown_manual_review"
        ],
        "blocked_sources": [
            asdict(decision) for decision in access_decisions if decision.access_status == "blocked"
        ],
        "permission_required_sources": [
            asdict(decision)
            for decision in access_decisions
            if decision.access_status == "permission_required"
        ],
        "production_parser_ready_sources": production_parser_ready_sources,
        "enrichment_summary": {
            "evidence_files_count": len(evidence_path_list),
            "evidence_domains_count": len(evidence_by_domain),
            "records_enriched_count": sum(
                1 for record in records if _find_evidence_for_record(record, evidence_by_domain)
            ),
            "records_with_platform_after_enrichment": sum(
                1 for record in enriched_records if normalize_key(record.detected_platform) not in UNKNOWN_VALUES
            ),
            "records_still_unknown_after_enrichment": sum(
                1 for result in fingerprint_results if result.delivery_mode == "unknown_manual_review"
            ),
        },
        "is_active_audit": audit_is_active_distribution(source_path),
        "baseline_delivery_fingerprint": summarize_delivery_fingerprints(raw_fingerprint_results),
    }


def audit_is_active_distribution(source_master_path: Path | str) -> dict[str, object]:
    path = Path(source_master_path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    buckets = Counter(_active_bucket(row.get("is_active")) for row in rows)
    legal_by_active: dict[str, dict[str, int]] = {}
    aanbod_by_active: dict[str, dict[str, int]] = {}
    valid_by_active: dict[str, int] = {}
    for bucket in ("true", "false", "empty"):
        bucket_rows = [row for row in rows if _active_bucket(row.get("is_active")) == bucket]
        legal_by_active[bucket] = _sorted_counts(
            Counter(normalize_key(row.get("legal_status")) or "empty" for row in bucket_rows)
        )
        aanbod_by_active[bucket] = _sorted_counts(
            Counter(
                normalize_key(row.get("aanbod_url_status") or row.get("aanbod_url_quality")) or "empty"
                for row in bucket_rows
            )
        )
        valid_by_active[bucket] = sum(1 for row in bucket_rows if _has_valid_aanbod(row))

    inactive_allowed_valid_count = sum(
        1
        for row in rows
        if _active_bucket(row.get("is_active")) == "false"
        and normalize_key(row.get("legal_status")) == "allowed_official_source"
        and _has_valid_aanbod(row)
    )
    return {
        "total_rows": len(rows),
        "is_active": _sorted_counts(buckets),
        "legal_status_by_is_active": legal_by_active,
        "aanbod_url_status_by_is_active": aanbod_by_active,
        "valid_aanbod_count_by_is_active": valid_by_active,
        "inactive_allowed_valid_count": inactive_allowed_valid_count,
        "semantic_adjustment_applied": False,
        "semantic_adjustment_reason": (
            "No inactive rows combine legal_status=allowed_official_source with valid aanbod."
        ),
    }


def _normalize_evidence_row(row: Mapping[str, str], csv_path: Path) -> dict[str, Any]:
    normalized_row = {normalize_key(key): normalize_text(value) for key, value in row.items()}
    domains = {
        domain
        for key in DOMAIN_COLUMNS
        for domain in [normalize_domain(normalized_row.get(key))]
        if domain
    }

    detected_platform = _first_value(normalized_row, PLATFORM_COLUMNS)
    delivery_mode = _canonical_delivery_mode(_first_value(normalized_row, DELIVERY_MODE_COLUMNS))
    parser_family_candidate = _canonical_parser_family(_first_value(normalized_row, PARSER_FAMILY_COLUMNS))
    confidence = _confidence(normalized_row)
    evidence_text = _join_values(normalized_row, EVIDENCE_COLUMNS)
    technology_signals = _join_values(normalized_row, TECHNOLOGY_SIGNAL_COLUMNS)

    has_iframe = parse_bool(normalized_row.get("has_iframe")) or bool(normalized_row.get("iframe_domain"))
    booleans = {key: parse_bool(normalized_row.get(key)) for key in BOOLEAN_COLUMNS}
    booleans["has_iframe"] = booleans["has_iframe"] or has_iframe
    booleans["has_json_ld"] = booleans["has_json_ld"] or parse_bool(normalized_row.get("json_ld_found"))
    booleans["has_visible_cards"] = booleans["has_visible_cards"] or _positive_int(
        normalized_row.get("card_count_estimate")
    )
    booleans["is_funda_dependent"] = booleans["is_funda_dependent"] or parse_bool(
        normalized_row.get("iframe_funda_detected")
    )
    booleans["has_wp_json"] = booleans["has_wp_json"] or normalize_key(normalized_row.get("wp_json_status")) in {
        "ok",
        "detected",
        "true",
    }

    return {
        "domains": domains,
        "detected_platform": detected_platform,
        "delivery_mode": delivery_mode,
        "parser_family_candidate": parser_family_candidate,
        "technology_signals": technology_signals,
        "evidence": evidence_text,
        "iframe_domain": normalize_domain(normalized_row.get("iframe_domain")),
        "confidence": confidence,
        "source_path": str(csv_path),
        **booleans,
    }


def _merge_evidence(
    current: Mapping[str, Any] | None,
    incoming: Mapping[str, Any],
) -> dict[str, Any]:
    if not current:
        merged = dict(incoming)
        merged["domains"] = set(incoming.get("domains", set()))
        return merged

    merged = dict(current)
    merged["domains"] = set(current.get("domains", set())) | set(incoming.get("domains", set()))
    current_confidence = float(current.get("confidence") or 0.0)
    incoming_confidence = float(incoming.get("confidence") or 0.0)

    for key in ("detected_platform", "delivery_mode", "parser_family_candidate"):
        if _should_replace_signal(merged.get(key), incoming.get(key), current_confidence, incoming_confidence):
            merged[key] = incoming.get(key)

    for key in BOOLEAN_COLUMNS:
        merged[key] = bool(merged.get(key)) or bool(incoming.get(key))

    if incoming_confidence > current_confidence:
        merged["confidence"] = incoming_confidence
    for key in ("technology_signals", "evidence", "source_path"):
        merged[key] = _merge_text(merged.get(key), incoming.get(key))
    if incoming.get("iframe_domain") and not merged.get("iframe_domain"):
        merged["iframe_domain"] = incoming.get("iframe_domain")
    return merged


def _apply_evidence(record: SourceIntelligenceRecord, evidence: Mapping[str, Any]) -> None:
    confidence = float(evidence.get("confidence") or 0.0)
    if _should_replace_signal(record.detected_platform, evidence.get("detected_platform"), record.delivery_mode_confidence, confidence):
        record.detected_platform = normalize_text(evidence.get("detected_platform"))
    if _should_replace_signal(record.delivery_mode, evidence.get("delivery_mode"), record.delivery_mode_confidence, confidence):
        record.delivery_mode = normalize_text(evidence.get("delivery_mode"))
    if _should_replace_signal(
        record.parser_family_candidate,
        evidence.get("parser_family_candidate"),
        record.delivery_mode_confidence,
        confidence,
    ):
        record.parser_family_candidate = normalize_text(evidence.get("parser_family_candidate"))
    if confidence > record.delivery_mode_confidence:
        record.delivery_mode_confidence = confidence

    for key in BOOLEAN_COLUMNS:
        if bool(evidence.get(key)):
            setattr(record, key, True)
    if evidence.get("iframe_domain") and not record.iframe_domain:
        record.iframe_domain = normalize_text(evidence.get("iframe_domain"))
    record.technology_signals = _merge_text(record.technology_signals, evidence.get("technology_signals"))
    record.evidence = _merge_text(record.evidence, evidence.get("evidence"))
    if any(bool(evidence.get(key)) for key in BLOCKER_FIELDS):
        record.notes = _merge_text(record.notes, "evidence_enrichment_blocker_preserved")


def _find_evidence_for_record(
    record: SourceIntelligenceRecord,
    evidence_by_domain: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    for domain in _domains_for_record(record):
        evidence = evidence_by_domain.get(domain)
        if evidence:
            return evidence
    return None


def _domains_for_record(record: SourceIntelligenceRecord) -> tuple[str, ...]:
    domains = [
        normalize_domain(record.source_domain),
        normalize_domain(record.homepage_url),
        normalize_domain(record.aanbod_url),
    ]
    return tuple(domain for domain in domains if domain)


def _first_value(row: Mapping[str, str], keys: Iterable[str]) -> str:
    for key in keys:
        value = normalize_text(row.get(key))
        if value:
            return value
    return ""


def _join_values(row: Mapping[str, str], keys: Iterable[str]) -> str:
    return " | ".join(value for key in keys for value in [normalize_text(row.get(key))] if value)


def _merge_text(current: object, incoming: object) -> str:
    parts: list[str] = []
    for value in (normalize_text(current), normalize_text(incoming)):
        if not value:
            continue
        for part in [item.strip() for item in value.split(" | ") if item.strip()]:
            if part not in parts:
                parts.append(part)
    return " | ".join(parts)


def _should_replace_signal(
    current: object,
    incoming: object,
    current_confidence: float,
    incoming_confidence: float,
) -> bool:
    incoming_key = normalize_key(incoming)
    current_key = normalize_key(current)
    if incoming_key in UNKNOWN_VALUES:
        return False
    if current_key in UNKNOWN_VALUES:
        return True
    return incoming_confidence > current_confidence


def _canonical_delivery_mode(value: object) -> str:
    key = normalize_key(value)
    return {
        "realworks": "realworks_public",
        "ogonline": "ogonline_xhr",
        "og online": "ogonline_xhr",
        "kolibri": "kolibri_public",
        "wordpress_cards": "wordpress_html_cards",
        "html_static_cards": "static_html_cards",
        "iframe_funda_blocked": "funda_iframe_blocked",
        "iframe_funda": "funda_iframe_blocked",
    }.get(key, normalize_text(value))


def _canonical_parser_family(value: object) -> str:
    key = normalize_key(value)
    return {
        "realworks": "realworks_public",
        "wordpress_cards": "wordpress_html_cards",
        "html_static_cards": "static_html_cards",
    }.get(key, normalize_text(value))


def _confidence(row: Mapping[str, str]) -> float:
    for key in CONFIDENCE_COLUMNS:
        value = parse_float(row.get(key))
        if value > 1.0:
            return min(value / 100.0, 1.0)
        if value > 0:
            return value
    return 0.0


def _positive_int(value: object) -> bool:
    try:
        return int(float(normalize_text(value) or "0")) > 0
    except ValueError:
        return False


def _active_bucket(value: object) -> str:
    normalized = normalize_key(value)
    if normalized in {"1", "true", "yes", "y", "ja"}:
        return "true"
    if normalized in {"0", "false", "no", "n", "nee"}:
        return "false"
    return "empty"


def _has_valid_aanbod(row: Mapping[str, str]) -> bool:
    return bool(normalize_text(row.get("aanbod_url"))) and normalize_key(
        row.get("aanbod_url_status") or row.get("aanbod_url_quality")
    ) == "valid"


def _top_counts(values: Iterable[str]) -> list[dict[str, object]]:
    counter = Counter(values)
    return [
        {"parser_family_candidate": key, "source_count": count}
        for key, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]


def _sorted_counts(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items(), key=lambda item: item[0]))
