from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.sources import (
    SourceIntelligenceRecord,
    fingerprint_delivery_mode,
    fingerprint_sources,
    load_source_intelligence_csv,
    summarize_delivery_fingerprints,
)


FIXTURE_PATH = Path("tests/fixtures/sources/source_intelligence_seed.csv")


def _record(**overrides: object) -> SourceIntelligenceRecord:
    values = {
        "source_id": "source-1",
        "source_domain": "example.nl",
        "access_status": "allowed",
    }
    values.update(overrides)
    return SourceIntelligenceRecord(**values)


def test_realworks_classifies_as_realworks_public() -> None:
    result = fingerprint_delivery_mode(_record(detected_platform="Realworks"))

    assert result.delivery_mode == "realworks_public"
    assert result.parser_family_candidate == "realworks_public"
    assert "realworks" in result.evidence_signals
    assert result.can_proceed_to_parser_family is True


def test_ogonline_classifies_as_ogonline_xhr() -> None:
    result = fingerprint_delivery_mode(_record(technology_signals="OG-online public xhr"))

    assert result.delivery_mode == "ogonline_xhr"
    assert result.parser_family_candidate == "ogonline_xhr"
    assert "ogonline" in result.evidence_signals


def test_kolibri_classifies_as_kolibri_public() -> None:
    result = fingerprint_delivery_mode(_record(detected_platform="Kolibri"))

    assert result.delivery_mode == "kolibri_public"
    assert result.parser_family_candidate == "kolibri_public"
    assert "kolibri" in result.evidence_signals


def test_wordpress_with_wp_json_classifies_as_wordpress_rest() -> None:
    result = fingerprint_delivery_mode(_record(detected_platform="WordPress", has_wp_json=True))

    assert result.delivery_mode == "wordpress_rest"
    assert result.parser_family_candidate == "wordpress_rest"
    assert result.evidence_signals == ("wordpress", "wp_json")


def test_wordpress_without_wp_json_classifies_as_wordpress_html_cards() -> None:
    result = fingerprint_delivery_mode(_record(detected_platform="WordPress", has_visible_cards=True))

    assert result.delivery_mode == "wordpress_html_cards"
    assert result.parser_family_candidate == "wordpress_html_cards"


def test_json_ld_classifies_when_no_stronger_signal_exists() -> None:
    result = fingerprint_delivery_mode(_record(has_json_ld=True, has_visible_cards=True))

    assert result.delivery_mode == "json_ld"
    assert result.parser_family_candidate == "json_ld"
    assert result.confidence >= 0.60


def test_sitemap_classifies_when_no_stronger_signal_exists() -> None:
    result = fingerprint_delivery_mode(_record(has_sitemap=True, has_visible_cards=True))

    assert result.delivery_mode == "sitemap_detail"
    assert result.parser_family_candidate == "sitemap_detail"
    assert result.confidence >= 0.55


def test_visible_cards_classifies_as_static_html_cards() -> None:
    result = fingerprint_delivery_mode(_record(has_visible_cards=True))

    assert result.delivery_mode == "static_html_cards"
    assert result.parser_family_candidate == "static_html_cards"
    assert "visible_cards" in result.evidence_signals


def test_funda_is_blocked_and_cannot_proceed() -> None:
    result = fingerprint_delivery_mode(_record(is_funda_dependent=True, detected_platform="Realworks"))

    assert result.delivery_mode == "funda_iframe_blocked"
    assert result.parser_family_candidate == "iframe_blocked_handler"
    assert result.confidence >= 0.95
    assert "funda_dependency" in result.blocking_signals
    assert result.can_proceed_to_parser_family is False


def test_pararius_is_blocked_and_cannot_proceed() -> None:
    result = fingerprint_delivery_mode(_record(is_pararius_dependent=True))

    assert result.delivery_mode == "pararius_external_blocked"
    assert result.parser_family_candidate == "iframe_blocked_handler"
    assert result.confidence >= 0.90
    assert "pararius_dependency" in result.blocking_signals
    assert result.can_proceed_to_parser_family is False


def test_captcha_is_blocked_and_cannot_proceed() -> None:
    result = fingerprint_delivery_mode(_record(has_captcha=True, detected_platform="Realworks"))

    assert result.delivery_mode == "captcha_blocked"
    assert result.parser_family_candidate == ""
    assert "captcha" in result.blocking_signals
    assert result.can_proceed_to_parser_family is False


def test_login_is_blocked_and_cannot_proceed() -> None:
    result = fingerprint_delivery_mode(_record(has_login=True, detected_platform="Realworks"))

    assert result.delivery_mode == "login_required"
    assert result.parser_family_candidate == ""
    assert "login_required" in result.blocking_signals
    assert result.can_proceed_to_parser_family is False


def test_403_cannot_proceed() -> None:
    result = fingerprint_delivery_mode(_record(has_403=True, detected_platform="Realworks"))

    assert result.delivery_mode == "unknown_manual_review"
    assert result.parser_family_candidate == ""
    assert "http_403" in result.blocking_signals
    assert result.can_proceed_to_parser_family is False


def test_access_policy_blocks_even_with_parser_signals() -> None:
    result = fingerprint_delivery_mode(
        _record(access_status="legal_review", detected_platform="Realworks", has_visible_cards=True)
    )

    assert result.delivery_mode == "realworks_public"
    assert result.parser_family_candidate == "realworks_public"
    assert result.access_status == "legal_review"
    assert result.can_proceed_to_parser_family is False
    assert "legal_review" in result.blocking_signals


def test_unknown_remains_manual_review() -> None:
    result = fingerprint_delivery_mode(_record(access_status="researching"))

    assert result.delivery_mode == "unknown_manual_review"
    assert result.parser_family_candidate == ""
    assert result.confidence <= 0.30
    assert result.recommended_action == "manual_review_needed"
    assert result.can_proceed_to_parser_family is False


def test_fingerprint_sources_returns_one_result_per_record() -> None:
    records = [_record(source_id="one"), _record(source_id="two", detected_platform="Realworks")]

    results = fingerprint_sources(records)

    assert [result.source_id for result in results] == ["one", "two"]


def test_summary_counts_delivery_modes_parser_families_and_signals() -> None:
    results = fingerprint_sources(load_source_intelligence_csv(FIXTURE_PATH))
    summary = summarize_delivery_fingerprints(results)

    assert summary["total_sources"] == 12
    assert summary["counts_by_delivery_mode"]["realworks_public"] == 1
    assert summary["counts_by_parser_family_candidate"]["realworks_public"] == 1
    assert summary["blocking_signal_counts"]["captcha"] == 1
    assert summary["evidence_signal_counts"]["realworks"] == 1
    assert summary["production_parser_ready_count"] == 8


def test_summary_counts_recommended_actions_and_manual_review() -> None:
    results = fingerprint_sources(
        [
            _record(source_id="ready", detected_platform="Realworks"),
            _record(source_id="review", access_status="researching"),
            _record(source_id="blocked", has_captcha=True),
        ]
    )
    summary = summarize_delivery_fingerprints(results)

    assert summary["counts_by_recommended_action"] == {
        "blocked_no_bypass": 1,
        "build_source_config": 1,
        "manual_review_needed": 1,
    }
    assert summary["manual_review_count"] == 1
    assert summary["blocked_or_permission_count"] == 1


def test_confidence_stays_inside_probability_range() -> None:
    results = fingerprint_sources(load_source_intelligence_csv(FIXTURE_PATH))

    assert all(0.0 <= result.confidence <= 1.0 for result in results)
