from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.discovery.models import AanbodAuditAttempt, LiveAanbodAttempt, SourceCandidate
from domek_wonen.discovery.reporter import render_discovery_run_report, split_missing_expected_gemeenten


def test_split_missing_expected_gemeenten_separates_zero_candidates_vs_rejected_only() -> None:
    expected = ["Veldhoven", "Breda", "Tilburg"]
    discovered_sources = [
        SourceCandidate(
            office_name="Accepted Breda",
            gemeente="Breda",
            plaats="Breda",
            source_adapter="seed",
            status="valid",
        )
    ]
    rejected_candidates = [
        SourceCandidate(
            office_name="Rejected Veldhoven",
            gemeente="Veldhoven",
            plaats="Veldhoven",
            source_adapter="overpass",
            status="rejected",
        )
    ]

    result = split_missing_expected_gemeenten(expected, discovered_sources, rejected_candidates)

    assert result["missing_expected_with_no_candidates"] == ["Tilburg"]
    assert result["expected_with_candidates_but_no_accepted_sources"] == ["Veldhoven"]


def test_reporter_shows_failed_domains_from_live_attempts() -> None:
    report = render_discovery_run_report(
        province="Noord-Brabant",
        run_timestamp="20260613T000000Z",
        seed_count=0,
        generated_queries=[],
        overpass_status="ok",
        analyzed_results=[],
        overpass_candidates=[],
        discovered_sources=[],
        rejected_candidates=[],
        expected_gemeenten=[],
        deduped_candidates_count=0,
        skipped_candidates_count=0,
        external_candidates_found=0,
        external_discovery_enabled=True,
        overpass_raw_candidates=0,
        overpass_candidates_with_website=0,
        overpass_candidates_without_website=0,
        overpass_new_domains_added=0,
        overpass_duplicates_vs_seed=0,
        overpass_errors=[],
        live_aanbod_enabled=True,
        live_sites_attempted=1,
        live_sites_success=0,
        live_sites_failed=1,
        existing_valid_aanbod_kept=0,
        new_valid_aanbod_found=0,
        new_suspect_aanbod_found=0,
        live_attempts=[
            LiveAanbodAttempt(
                office_name="Failed Office",
                website="https://failed.example.nl",
                root_domain="failed.example.nl",
                gemeente="Breda",
                source_origin="overpass_osm",
                attempted=True,
                success=False,
                final_status="failed_fetch",
                final_aanbod_url="",
                detection_method="failed",
                detection_score=0,
                failure_stage="homepage_fetch",
                failure_reason="connection refused",
                http_status_homepage=0,
                http_status_sitemap=0,
                tested_urls_count=0,
                best_candidate_url="",
                best_candidate_reason="",
                elapsed_ms=12,
            )
        ],
        audit_aanbod_enabled=True,
        audited_sites_count=2,
        browser_audit_valid_found=1,
        browser_audit_suspect_found=0,
        browser_audit_missing_or_failed=1,
        browser_audit_unique_valid_domains=1,
        browser_audit_unique_valid_urls=1,
        browser_audit_duplicate_valid_rows=1,
        valid_aanbod_after_audit=1,
        missing_aanbod_after_audit=0,
        audit_attempts=[
            AanbodAuditAttempt(
                office_name="Audited Valid",
                website="https://valid.example.nl",
                root_domain="valid.example.nl",
                gemeente="Breda",
                final_status="valid",
                final_aanbod_url="https://valid.example.nl/aanbod",
                confidence=93,
                detection_method="homepage_link",
                homepage_status=200,
                homepage_title="Aanbod",
                candidates_found_count=2,
                candidates_tested_count=1,
                best_candidate_url="https://valid.example.nl/aanbod",
                final_page_type="listing_index",
                listing_signals_count=5,
                residential_signals_count=6,
                commercial_signals_count=0,
                residential_signals_found=["woning"],
                commercial_signals_found=[],
                page_quality_reason="residential_listing_index",
                listing_signals_found=["vraagprijs"],
                commercial_hard_block=False,
                commercial_block_reason="",
                is_duplicate_audit_result=False,
                rejection_reason="",
                elapsed_ms=10,
            ),
            AanbodAuditAttempt(
                office_name="Audited Duplicate",
                website="https://valid.example.nl",
                root_domain="valid.example.nl",
                gemeente="Tilburg",
                final_status="valid",
                final_aanbod_url="https://valid.example.nl/aanbod",
                confidence=91,
                detection_method="homepage_link",
                homepage_status=200,
                homepage_title="Aanbod",
                candidates_found_count=2,
                candidates_tested_count=1,
                best_candidate_url="https://valid.example.nl/aanbod",
                final_page_type="listing_index",
                listing_signals_count=5,
                residential_signals_count=6,
                commercial_signals_count=0,
                residential_signals_found=["woning"],
                commercial_signals_found=[],
                page_quality_reason="residential_listing_index",
                listing_signals_found=["vraagprijs"],
                commercial_hard_block=False,
                commercial_block_reason="",
                is_duplicate_audit_result=True,
                rejection_reason="",
                elapsed_ms=11,
            ),
            AanbodAuditAttempt(
                office_name="Audited Failed",
                website="https://failed.example.nl",
                root_domain="failed.example.nl",
                gemeente="Breda",
                final_status="failed_fetch",
                final_aanbod_url="",
                confidence=0,
                detection_method="failed",
                homepage_status=0,
                homepage_title="",
                candidates_found_count=0,
                candidates_tested_count=0,
                best_candidate_url="",
                final_page_type="unknown",
                listing_signals_count=0,
                residential_signals_count=0,
                commercial_signals_count=0,
                residential_signals_found=[],
                commercial_signals_found=[],
                page_quality_reason="failed_fetch",
                listing_signals_found=[],
                commercial_hard_block=False,
                commercial_block_reason="",
                is_duplicate_audit_result=False,
                rejection_reason="timeout",
                elapsed_ms=15,
            ),
        ],
        overpass_cache_used=False,
        overpass_cache_timestamp="",
        overpass_source_label="primary",
        source_master_rows=[
            {
                "is_active": "true",
                "aanbod_url_quality": "valid",
            },
            {
                "is_active": "false",
                "aanbod_url_quality": "suspect",
            },
        ],
        missing_website_review_count=1,
        website_resolver_resolved_count=1,
        website_resolver_unresolved_count=1,
        aggregator_registry_rows=[
            {"aggregator_name": "Huispedia", "adapter_enabled": "false", "permission_status": "needs_review"},
            {"aggregator_name": "Funda", "adapter_enabled": "false", "permission_status": "not_allowed_for_scraping"},
        ],
    )

    assert "Top failed domains" in report
    assert "failed.example.nl: 1" in report
    assert "## Aanbod Auditor Summary" in report
    assert "Browser audit valid found: 1" in report
    assert "Audit aanbod enabled: true" in report
    assert "Browser audit unique valid domains: 1" in report
    assert "Browser audit duplicate valid rows: 1" in report
    assert "Overpass Cache Status" in report
    assert "Source Master Summary" in report
    assert "WebsiteResolver Summary" in report
