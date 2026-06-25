from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.sources import (
    SourceIntelligenceRecord,
    decide_source_access,
    evaluate_source_access,
    summarize_access_decisions,
)


def _record(**overrides: object) -> SourceIntelligenceRecord:
    values = {
        "source_id": "source-1",
        "source_domain": "example.nl",
        "access_status": "researching",
    }
    values.update(overrides)
    return SourceIntelligenceRecord(**values)


def test_allowed_source_can_run_production() -> None:
    decision = decide_source_access(_record(access_status="allowed"))

    assert decision.access_status == "allowed"
    assert decision.can_run_production_extraction is True
    assert decision.can_run_research_probe is True
    assert decision.required_action == "use_with_configured_limits"
    assert decision.risk_flags == ()


def test_limited_source_can_run_production_with_limited_risk_flag() -> None:
    decision = decide_source_access(_record(access_status="limited"))

    assert decision.access_status == "limited"
    assert decision.can_run_production_extraction is True
    assert decision.can_run_research_probe is True
    assert decision.risk_flags == ("limited",)


def test_researching_source_can_only_run_research_probe() -> None:
    decision = decide_source_access(_record(access_status="researching"))

    assert decision.access_status == "researching"
    assert decision.can_run_production_extraction is False
    assert decision.can_run_research_probe is True
    assert decision.required_action == "manual_review"
    assert decision.risk_flags == ("insufficient_evidence",)


def test_unknown_source_can_only_run_research_probe() -> None:
    decision = decide_source_access(_record(access_status="unknown"))

    assert decision.access_status == "unknown"
    assert decision.can_run_production_extraction is False
    assert decision.can_run_research_probe is True
    assert decision.reason == "insufficient_access_evidence"


def test_legal_review_source_cannot_run_anything() -> None:
    decision = decide_source_access(_record(access_status="legal_review"))

    assert decision.access_status == "legal_review"
    assert decision.can_run_production_extraction is False
    assert decision.can_run_research_probe is False
    assert decision.required_action == "legal_review"


def test_terms_legal_review_overrides_research_probe() -> None:
    decision = decide_source_access(_record(access_status="allowed", terms_status="legal_review"))

    assert decision.access_status == "legal_review"
    assert decision.can_run_production_extraction is False
    assert decision.can_run_research_probe is False
    assert decision.risk_flags == ("legal_review",)


def test_disabled_source_cannot_run_anything() -> None:
    decision = decide_source_access(_record(access_status="disabled"))

    assert decision.access_status == "disabled"
    assert decision.can_run_production_extraction is False
    assert decision.can_run_research_probe is False
    assert decision.required_action == "disabled"


def test_funda_dependency_is_blocked_even_when_allowed() -> None:
    decision = decide_source_access(_record(access_status="allowed", is_funda_dependent=True))

    assert decision.access_status == "blocked"
    assert decision.reason == "funda_dependency_no_scraping"
    assert decision.required_action == "do_not_use"
    assert decision.risk_flags == ("funda_dependency",)


def test_funda_delivery_mode_is_blocked_even_when_allowed() -> None:
    decision = decide_source_access(_record(access_status="allowed", delivery_mode="funda_iframe_blocked"))

    assert decision.access_status == "blocked"
    assert decision.reason == "funda_dependency_no_scraping"


def test_pararius_dependency_requires_permission_even_when_allowed() -> None:
    decision = decide_source_access(_record(access_status="allowed", is_pararius_dependent=True))

    assert decision.access_status == "permission_required"
    assert decision.can_run_production_extraction is False
    assert decision.can_run_research_probe is False
    assert decision.required_action == "request_permission"
    assert decision.risk_flags == ("pararius_dependency",)


def test_captcha_always_blocks() -> None:
    decision = decide_source_access(_record(access_status="allowed", has_captcha=True))

    assert decision.access_status == "blocked"
    assert decision.reason == "captcha_blocked_no_bypass"
    assert decision.risk_flags == ("captcha",)


def test_login_required_requires_permission() -> None:
    decision = decide_source_access(_record(access_status="allowed", has_login=True))

    assert decision.access_status == "permission_required"
    assert decision.reason == "login_required"
    assert decision.required_action == "request_permission"
    assert decision.risk_flags == ("login_required",)


def test_has_403_blocks() -> None:
    decision = decide_source_access(_record(access_status="allowed", has_403=True))

    assert decision.access_status == "blocked"
    assert decision.reason == "http_403_blocked"
    assert decision.required_action == "do_not_use"
    assert decision.risk_flags == ("http_403",)


def test_blockers_have_priority_over_allowed() -> None:
    decision = decide_source_access(
        _record(
            access_status="allowed",
            terms_status="legal_review",
            has_captcha=True,
        )
    )

    assert decision.access_status == "blocked"
    assert decision.reason == "captcha_blocked_no_bypass"
    assert decision.risk_flags == ("captcha",)


def test_evaluate_source_access_returns_one_decision_per_record() -> None:
    records = [
        _record(source_id="allowed", access_status="allowed"),
        _record(source_id="unknown", access_status="unknown"),
        _record(source_id="captcha", has_captcha=True),
    ]

    decisions = evaluate_source_access(records)

    assert [decision.source_id for decision in decisions] == ["allowed", "unknown", "captcha"]


def test_summarize_access_decisions_counts_access_statuses() -> None:
    decisions = evaluate_source_access(
        [
            _record(source_id="allowed", access_status="allowed"),
            _record(source_id="limited", access_status="limited"),
            _record(source_id="unknown", access_status="unknown"),
            _record(source_id="captcha", has_captcha=True),
            _record(source_id="login", has_login=True),
            _record(source_id="legal", access_status="legal_review"),
        ]
    )

    summary = summarize_access_decisions(decisions)

    assert summary["total_sources"] == 6
    assert summary["counts_by_access_status"] == {
        "allowed": 1,
        "blocked": 1,
        "legal_review": 1,
        "limited": 1,
        "permission_required": 1,
        "unknown": 1,
    }
    assert summary["production_allowed_count"] == 2
    assert summary["research_allowed_count"] == 3
    assert summary["blocked_count"] == 1
    assert summary["permission_required_count"] == 1
    assert summary["legal_review_count"] == 1


def test_summarize_access_decisions_counts_risk_flags_and_required_actions() -> None:
    decisions = evaluate_source_access(
        [
            _record(source_id="limited", access_status="limited"),
            _record(source_id="unknown", access_status="unknown"),
            _record(source_id="captcha", has_captcha=True),
            _record(source_id="login", has_login=True),
            _record(source_id="pararius", is_pararius_dependent=True),
        ]
    )

    summary = summarize_access_decisions(decisions)

    assert summary["risk_flag_counts"] == {
        "captcha": 1,
        "insufficient_evidence": 1,
        "limited": 1,
        "login_required": 1,
        "pararius_dependency": 1,
    }
    assert summary["required_action_counts"] == {
        "do_not_use": 1,
        "manual_review": 1,
        "request_permission": 2,
        "use_with_limits": 1,
    }


def test_access_policy_module_imports_no_network_or_browser_libraries() -> None:
    module_text = Path("scraper/src/domek_wonen/sources/access_policy.py").read_text(encoding="utf-8")

    forbidden = ["requests", "httpx", "urllib.request", "urlopen", "playwright", "selenium"]
    assert not any(token in module_text for token in forbidden)
