from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable

from .access_policy import decide_source_access
from .source_intelligence_models import SourceIntelligenceRecord, normalize_key


BLOCKING_ACCESS_STATUSES = {"blocked", "permission_required", "legal_review", "disabled"}


@dataclass(frozen=True, slots=True)
class DeliveryFingerprintResult:
    source_id: str
    source_domain: str
    access_status: str
    delivery_mode: str
    parser_family_candidate: str
    confidence: float
    evidence_signals: tuple[str, ...]
    blocking_signals: tuple[str, ...]
    recommended_action: str
    can_proceed_to_parser_family: bool
    reason: str
    notes: str = ""


def fingerprint_delivery_mode(record: SourceIntelligenceRecord) -> DeliveryFingerprintResult:
    access_decision = decide_source_access(record)
    delivery_mode, parser_family_candidate, confidence, evidence_signals, blocking_signals, recommended_action = (
        _classify_delivery(record)
    )

    blocking = _dedupe((*access_decision.risk_flags, *blocking_signals))
    can_proceed = (
        access_decision.can_run_production_extraction
        and access_decision.access_status not in BLOCKING_ACCESS_STATUSES
        and bool(parser_family_candidate)
        and parser_family_candidate != "iframe_blocked_handler"
        and delivery_mode not in {
            "funda_iframe_blocked",
            "pararius_external_blocked",
            "captcha_blocked",
            "login_required",
            "iframe_external",
            "unknown_manual_review",
        }
    )

    if not access_decision.can_run_production_extraction:
        can_proceed = False
        if recommended_action not in {"blocked_no_bypass", "permission_required"}:
            recommended_action = _action_for_access_decision(access_decision.required_action)

    return DeliveryFingerprintResult(
        source_id=record.source_id,
        source_domain=record.source_domain,
        access_status=access_decision.access_status,
        delivery_mode=delivery_mode,
        parser_family_candidate=parser_family_candidate,
        confidence=_clamp_confidence(confidence),
        evidence_signals=evidence_signals,
        blocking_signals=blocking,
        recommended_action=recommended_action,
        can_proceed_to_parser_family=can_proceed,
        reason=access_decision.reason if not access_decision.can_run_production_extraction else _reason_for(delivery_mode),
        notes=record.notes,
    )


def fingerprint_sources(records: Iterable[SourceIntelligenceRecord]) -> list[DeliveryFingerprintResult]:
    return [fingerprint_delivery_mode(record) for record in records]


def summarize_delivery_fingerprints(results: Iterable[DeliveryFingerprintResult]) -> dict[str, object]:
    result_list = list(results)
    confidence_values: dict[str, list[float]] = defaultdict(list)
    for result in result_list:
        confidence_values[result.delivery_mode].append(result.confidence)

    return {
        "total_sources": len(result_list),
        "counts_by_delivery_mode": _sorted_counts(Counter(result.delivery_mode for result in result_list)),
        "counts_by_parser_family_candidate": _sorted_counts(
            Counter(result.parser_family_candidate for result in result_list)
        ),
        "counts_by_recommended_action": _sorted_counts(Counter(result.recommended_action for result in result_list)),
        "production_parser_ready_count": sum(1 for result in result_list if result.can_proceed_to_parser_family),
        "blocked_or_permission_count": sum(
            1
            for result in result_list
            if result.access_status in {"blocked", "permission_required", "legal_review", "disabled"}
        ),
        "manual_review_count": sum(
            1
            for result in result_list
            if result.recommended_action == "manual_review_needed" or result.delivery_mode == "unknown_manual_review"
        ),
        "average_confidence_by_delivery_mode": {
            mode: round(sum(values) / len(values), 4) for mode, values in sorted(confidence_values.items())
        },
        "blocking_signal_counts": _sorted_counts(
            Counter(signal for result in result_list for signal in result.blocking_signals)
        ),
        "evidence_signal_counts": _sorted_counts(
            Counter(signal for result in result_list for signal in result.evidence_signals)
        ),
    }


def _classify_delivery(
    record: SourceIntelligenceRecord,
) -> tuple[str, str, float, tuple[str, ...], tuple[str, ...], str]:
    platform_text = " ".join(
        part
        for part in (
            normalize_key(record.detected_platform),
            normalize_key(record.technology_signals),
            normalize_key(record.delivery_mode),
            normalize_key(record.parser_family_candidate),
        )
        if part
    )

    if record.is_funda_dependent or record.delivery_mode == "funda_iframe_blocked":
        return ("funda_iframe_blocked", "iframe_blocked_handler", 0.97, ("iframe",), ("funda_dependency",), "blocked_no_bypass")
    if record.is_pararius_dependent or record.delivery_mode == "pararius_external_blocked":
        return (
            "pararius_external_blocked",
            "iframe_blocked_handler",
            0.94,
            ("iframe",),
            ("pararius_dependency",),
            "permission_required",
        )
    if record.has_captcha:
        return ("captcha_blocked", "", 0.99, (), ("captcha",), "blocked_no_bypass")
    if record.has_login:
        return ("login_required", "", 0.96, (), ("login_required",), "permission_required")
    if record.has_403:
        return ("unknown_manual_review", "", 0.90, (), ("http_403",), "blocked_no_bypass")
    if "realworks" in platform_text:
        return ("realworks_public", "realworks_public", 0.86, ("realworks",), (), "build_source_config")
    if _contains_any(platform_text, ("ogonline", "og online", "og-online")):
        return ("ogonline_xhr", "ogonline_xhr", 0.84, ("ogonline",), (), "build_source_config")
    if "kolibri" in platform_text:
        return ("kolibri_public", "kolibri_public", 0.78, ("kolibri",), (), "research_before_parser")
    if _contains_any(platform_text, ("wordpress", "wp")) and record.has_wp_json:
        return ("wordpress_rest", "wordpress_rest", 0.78, ("wordpress", "wp_json"), (), "build_source_config")
    if _contains_any(platform_text, ("wordpress", "wp")):
        return ("wordpress_html_cards", "wordpress_html_cards", 0.68, ("wordpress",), (), "build_source_config")
    if record.has_json_ld:
        return ("json_ld", "json_ld", 0.63, ("json_ld",), (), "build_source_config")
    if record.has_sitemap:
        return ("sitemap_detail", "sitemap_detail", 0.58, ("sitemap",), (), "research_before_parser")
    if record.has_visible_cards:
        return ("static_html_cards", "static_html_cards", 0.57, ("visible_cards",), (), "build_source_config")
    if record.has_iframe:
        return ("iframe_external", "iframe_blocked_handler", 0.52, ("iframe",), (), "manual_review_needed")

    return ("unknown_manual_review", "", 0.25, (), (), "manual_review_needed")


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)


def _clamp_confidence(value: float) -> float:
    return max(0.0, min(1.0, value))


def _action_for_access_decision(required_action: str) -> str:
    return {
        "do_not_use": "blocked_no_bypass",
        "request_permission": "permission_required",
        "legal_review": "legal_review",
        "disabled": "disabled",
        "manual_review": "manual_review_needed",
    }.get(required_action, required_action or "manual_review_needed")


def _reason_for(delivery_mode: str) -> str:
    return {
        "realworks_public": "realworks_evidence",
        "ogonline_xhr": "ogonline_evidence",
        "kolibri_public": "kolibri_evidence",
        "wordpress_rest": "wordpress_rest_evidence",
        "wordpress_html_cards": "wordpress_html_cards_evidence",
        "json_ld": "json_ld_evidence",
        "sitemap_detail": "sitemap_evidence",
        "static_html_cards": "visible_cards_evidence",
        "iframe_external": "iframe_requires_manual_review",
        "unknown_manual_review": "insufficient_delivery_evidence",
    }.get(delivery_mode, "delivery_mode_fingerprint")


def _sorted_counts(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items(), key=lambda item: item[0]))
