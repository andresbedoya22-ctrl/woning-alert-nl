from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from .source_intelligence_models import SourceIntelligenceRecord, normalize_key


ALLOWED_ACCESS_STATUSES = {
    "allowed",
    "limited",
    "permission_required",
    "legal_review",
    "blocked",
    "disabled",
    "researching",
    "unknown",
}


@dataclass(frozen=True, slots=True)
class AccessPolicyDecision:
    source_id: str
    source_domain: str
    access_status: str
    can_run_production_extraction: bool
    can_run_research_probe: bool
    reason: str
    required_action: str
    risk_flags: tuple[str, ...]
    notes: str = ""


def decide_source_access(record: SourceIntelligenceRecord) -> AccessPolicyDecision:
    access_status = normalize_key(record.access_status)
    terms_status = normalize_key(record.terms_status)
    delivery_mode = normalize_key(record.delivery_mode)
    recommended_action = normalize_key(record.recommended_action)

    if (
        record.is_funda_dependent
        or delivery_mode == "funda_iframe_blocked"
        or recommended_action == "blocked_no_bypass"
    ):
        return _decision(record, "blocked", False, False, "funda_dependency_no_scraping", "do_not_use", ("funda_dependency",))

    if record.is_pararius_dependent or delivery_mode == "pararius_external_blocked":
        return _decision(
            record,
            "permission_required",
            False,
            False,
            "pararius_requires_permission",
            "request_permission",
            ("pararius_dependency",),
        )

    if record.has_captcha:
        return _decision(record, "blocked", False, False, "captcha_blocked_no_bypass", "do_not_use", ("captcha",))

    if record.has_login:
        return _decision(
            record,
            "permission_required",
            False,
            False,
            "login_required",
            "request_permission",
            ("login_required",),
        )

    if record.has_403:
        return _decision(record, "blocked", False, False, "http_403_blocked", "do_not_use", ("http_403",))

    if access_status == "legal_review" or terms_status == "legal_review":
        return _decision(
            record,
            "legal_review",
            False,
            False,
            "legal_review_required",
            "legal_review",
            ("legal_review",),
        )

    if access_status == "disabled":
        return _decision(record, "disabled", False, False, "source_disabled", "disabled", ("disabled",))

    if access_status == "allowed":
        return _decision(
            record,
            "allowed",
            True,
            True,
            "allowed_by_source_record",
            "use_with_configured_limits",
            (),
        )

    if access_status == "limited":
        return _decision(record, "limited", True, True, "limited_by_source_record", "use_with_limits", ("limited",))

    fallback_status = access_status if access_status in {"researching", "unknown"} else "researching"
    return _decision(
        record,
        fallback_status,
        False,
        True,
        "insufficient_access_evidence",
        "manual_review",
        ("insufficient_evidence",),
    )


def evaluate_source_access(records: Iterable[SourceIntelligenceRecord]) -> list[AccessPolicyDecision]:
    return [decide_source_access(record) for record in records]


def summarize_access_decisions(decisions: Iterable[AccessPolicyDecision]) -> dict[str, object]:
    decision_list = list(decisions)
    risk_flag_counts = Counter(flag for decision in decision_list for flag in decision.risk_flags)
    counts_by_access_status = Counter(decision.access_status for decision in decision_list)
    required_action_counts = Counter(decision.required_action for decision in decision_list)

    return {
        "total_sources": len(decision_list),
        "counts_by_access_status": _sorted_counts(counts_by_access_status),
        "production_allowed_count": sum(1 for decision in decision_list if decision.can_run_production_extraction),
        "research_allowed_count": sum(1 for decision in decision_list if decision.can_run_research_probe),
        "blocked_count": counts_by_access_status.get("blocked", 0),
        "permission_required_count": counts_by_access_status.get("permission_required", 0),
        "legal_review_count": counts_by_access_status.get("legal_review", 0),
        "risk_flag_counts": _sorted_counts(risk_flag_counts),
        "required_action_counts": _sorted_counts(required_action_counts),
    }


def _decision(
    record: SourceIntelligenceRecord,
    access_status: str,
    can_run_production_extraction: bool,
    can_run_research_probe: bool,
    reason: str,
    required_action: str,
    risk_flags: tuple[str, ...],
    notes: str = "",
) -> AccessPolicyDecision:
    return AccessPolicyDecision(
        source_id=record.source_id,
        source_domain=record.source_domain,
        access_status=access_status,
        can_run_production_extraction=can_run_production_extraction,
        can_run_research_probe=can_run_research_probe,
        reason=reason,
        required_action=required_action,
        risk_flags=risk_flags,
        notes=notes,
    )


def _sorted_counts(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items(), key=lambda item: item[0]))
