from __future__ import annotations

import csv
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .aanbod_auditor import AanbodAuditor
from .aanbod_finder import (
    apply_aanbod_classification,
    classify_aanbod_url,
    detect_live_aanbod_url,
    suggest_common_aanbod_paths,
)
from .config import DEFAULT_AGGREGATOR_LEGAL_REGISTRY_PATH, DEFAULT_GEMEENTEN_REFERENCE_PATH, DISCOVERY_BASE_DIR
from .dedupe import dedupe_candidates
from .models import AanbodAuditAttempt, DiscoveryResult, GeneratedQuery, LiveAanbodAttempt, SourceCandidate
from .overpass_adapter import OverpassAdapter, OverpassDiscoveryResponse
from .query_generator import generate_queries_from_reference
from .reporter import load_expected_gemeenten, render_discovery_run_report, write_discovery_run_report
from .scorer import score_candidate
from .seed_adapter import load_seed_candidates
from .source_master_builder import build_source_master_rows, write_source_master
from .website_resolver import resolve_websites
from .website_analyzer import analyze_candidate_website
from .website_fetcher import WebsiteFetcher


RUNS_DIR = DISCOVERY_BASE_DIR / "data" / "discovery" / "runs"
LATEST_DIR = DISCOVERY_BASE_DIR / "data" / "discovery" / "latest"


@dataclass(slots=True)
class DiscoveryEngineOutput:
    run_timestamp: str
    run_dir: Path
    latest_dir: Path
    report_path: Path
    overpass_status: str
    seed_count: int
    generated_queries_count: int
    analyzed_candidates_count: int
    discovered_sources_count: int
    rejected_candidates_count: int
    deduped_candidates_count: int
    skipped_candidates_count: int
    external_candidates_found: int
    external_discovery_enabled: bool
    overpass_raw_candidates: int
    overpass_candidates_with_website: int
    overpass_candidates_without_website: int
    overpass_new_domains_added: int
    overpass_duplicates_vs_seed: int
    live_aanbod_enabled: bool
    live_sites_attempted: int
    live_sites_success: int
    live_sites_failed: int
    existing_valid_aanbod_kept: int
    new_valid_aanbod_found: int
    new_suspect_aanbod_found: int
    still_missing_aanbod: int


def normalize_province_name(value: str) -> str:
    normalized = (value or "").strip().lower().replace("_", "-").replace(" ", "-")
    aliases = {
        "noord-brabant": "Noord-Brabant",
    }
    return aliases.get(normalized, (value or "").strip())


def _candidate_to_row(candidate: SourceCandidate) -> dict[str, str]:
    return {
        "office_name": candidate.office_name,
        "website": candidate.website,
        "root_domain": candidate.root_domain,
        "raw_place": candidate.raw_place,
        "normalized_place": candidate.normalized_place,
        "gemeente": candidate.gemeente,
        "plaats": candidate.plaats,
        "place_status": candidate.place_status,
        "place_review_reason": candidate.place_review_reason,
        "provincie": candidate.provincie,
        "aanbod_url": candidate.aanbod_url,
        "aanbod_url_quality": candidate.aanbod_url_quality,
        "aanbod_url_type": candidate.aanbod_url_type,
        "aanbod_detection_method": candidate.aanbod_detection_method,
        "aanbod_detection_score": str(candidate.aanbod_detection_score),
        "aanbod_validation_reason": candidate.aanbod_validation_reason,
        "confidence": f"{candidate.confidence:.2f}",
        "needs_review": "true" if candidate.needs_review else "false",
        "source_adapter": candidate.source_adapter,
        "source_origin": candidate.source_origin,
        "score": str(candidate.score),
        "status": candidate.status,
        "review_reason": candidate.review_reason,
        "rejection_reason": candidate.rejection_reason,
        "notes": candidate.notes,
        "osm_type": candidate.osm_type,
        "osm_id": candidate.osm_id,
        "osm_website": candidate.osm_website,
        "osm_contact_website": candidate.osm_contact_website,
        "osm_city": candidate.osm_city,
        "osm_postcode": candidate.osm_postcode,
        "osm_phone": candidate.osm_phone,
        "osm_contact_phone": candidate.osm_contact_phone,
        "osm_email": candidate.osm_email,
        "osm_contact_email": candidate.osm_contact_email,
        "osm_lat": candidate.osm_lat,
        "osm_lon": candidate.osm_lon,
        "evidence": " | ".join(candidate.evidence),
    }


def _query_to_row(query: GeneratedQuery) -> dict[str, str]:
    return {
        "gemeente": query.gemeente,
        "provincie": query.provincie,
        "template": query.template,
        "query": query.query,
    }


def _live_attempt_to_row(attempt: LiveAanbodAttempt) -> dict[str, str]:
    return {
        "office_name": attempt.office_name,
        "website": attempt.website,
        "root_domain": attempt.root_domain,
        "gemeente": attempt.gemeente,
        "source_origin": attempt.source_origin,
        "attempted": "true" if attempt.attempted else "false",
        "success": "true" if attempt.success else "false",
        "final_status": attempt.final_status,
        "final_aanbod_url": attempt.final_aanbod_url,
        "detection_method": attempt.detection_method,
        "detection_score": str(attempt.detection_score),
        "failure_stage": attempt.failure_stage,
        "failure_reason": attempt.failure_reason,
        "http_status_homepage": str(attempt.http_status_homepage),
        "http_status_sitemap": str(attempt.http_status_sitemap),
        "tested_urls_count": str(attempt.tested_urls_count),
        "best_candidate_url": attempt.best_candidate_url,
        "best_candidate_reason": attempt.best_candidate_reason,
        "elapsed_ms": str(attempt.elapsed_ms),
    }


def _audit_attempt_to_row(attempt) -> dict[str, str]:
    return {
        "office_name": attempt.office_name,
        "website": attempt.website,
        "root_domain": attempt.root_domain,
        "gemeente": attempt.gemeente,
        "final_status": attempt.final_status,
        "final_aanbod_url": attempt.final_aanbod_url,
        "confidence": str(attempt.confidence),
        "detection_method": attempt.detection_method,
        "homepage_status": str(attempt.homepage_status),
        "homepage_title": attempt.homepage_title,
        "candidates_found_count": str(attempt.candidates_found_count),
        "candidates_tested_count": str(attempt.candidates_tested_count),
        "best_candidate_url": attempt.best_candidate_url,
        "final_page_type": attempt.final_page_type,
        "residential_signals_count": str(attempt.residential_signals_count),
        "residential_signals_found": ",".join(attempt.residential_signals_found),
        "commercial_signals_count": str(attempt.commercial_signals_count),
        "commercial_signals_found": ",".join(attempt.commercial_signals_found),
        "page_quality_reason": attempt.page_quality_reason,
        "commercial_hard_block": "true" if attempt.commercial_hard_block else "false",
        "commercial_block_reason": attempt.commercial_block_reason,
        "is_duplicate_audit_result": "true" if attempt.is_duplicate_audit_result else "false",
        "listing_signals_count": str(attempt.listing_signals_count),
        "listing_signals_found": ",".join(attempt.listing_signals_found),
        "rejection_reason": attempt.rejection_reason,
        "elapsed_ms": str(attempt.elapsed_ms),
    }


def _manual_website_review_fieldnames() -> list[str]:
    return [
        "office_name",
        "gemeente",
        "plaats",
        "source_origin",
        "raw_place",
        "normalized_place",
        "phone",
        "email",
        "lat",
        "lon",
        "reason",
        "suggested_domains",
        "notes",
    ]


def _load_aggregator_registry_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _copy_to_latest(run_dir: Path, latest_dir: Path, filenames: list[str]) -> None:
    latest_dir.mkdir(parents=True, exist_ok=True)
    for filename in filenames:
        shutil.copy2(run_dir / filename, latest_dir / filename)


def _create_run_dir(base_dir: Path, run_timestamp: str) -> tuple[str, Path]:
    run_id = run_timestamp
    run_dir = base_dir / run_id
    suffix = 1
    while run_dir.exists():
        run_id = f"{run_timestamp}-{suffix:02d}"
        run_dir = base_dir / run_id
        suffix += 1
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_id, run_dir


def _enrich_candidate(candidate: SourceCandidate) -> DiscoveryResult:
    website_analysis = analyze_candidate_website(candidate)
    aanbod_classification = classify_aanbod_url(candidate.aanbod_url)
    if not candidate.aanbod_validation_reason:
        apply_aanbod_classification(candidate, aanbod_classification)

    evidence: list[str] = []
    evidence.append(f"website_exists={str(website_analysis.website_exists).lower()}")
    if website_analysis.makelaar_signals:
        evidence.append("makelaar_signals=" + ",".join(website_analysis.makelaar_signals))
    evidence.append(f"aanbod_url_status={candidate.aanbod_url_quality}")
    evidence.append(f"aanbod_url_reason={candidate.aanbod_validation_reason or aanbod_classification.reason}")
    evidence.append(f"aanbod_detection_method={candidate.aanbod_detection_method}")
    evidence.append(f"aanbod_detection_score={candidate.aanbod_detection_score}")

    if not candidate.aanbod_url and candidate.website:
        suggestions = suggest_common_aanbod_paths(candidate.website)
        if suggestions:
            evidence.append("suggested_aanbod_paths=" + ",".join(suggestions[:3]))

    reasons = [candidate.review_reason] if candidate.review_reason else []
    if candidate.needs_review and not reasons:
        reasons.append("needs_review=true from source")
    reasons.append(candidate.aanbod_validation_reason or aanbod_classification.reason)

    candidate.evidence = [item for item in evidence if item]
    candidate.review_reason = "; ".join(dict.fromkeys(reason for reason in reasons if reason))

    score_result = score_candidate(candidate)
    candidate.score = score_result.score
    candidate.status = score_result.status
    if candidate.status == "rejected" and not candidate.rejection_reason:
        candidate.rejection_reason = "scored_rejected"
    return DiscoveryResult(candidate=candidate, score=score_result.score, status=score_result.status, reasons=score_result.reasons)


def _mark_missing_website(candidate: SourceCandidate) -> DiscoveryResult:
    candidate.status = "rejected"
    candidate.score = 0
    candidate.aanbod_url_quality = "missing"
    candidate.aanbod_detection_method = "failed"
    candidate.aanbod_detection_score = 0
    candidate.website_resolution_status = candidate.website_resolution_status or "needs_manual_review"
    candidate.aanbod_validation_reason = "missing website"
    candidate.rejection_reason = "missing_website"
    candidate.review_reason = "; ".join(
        part for part in (candidate.review_reason, "missing website in Overpass candidate") if part
    )
    candidate.evidence = ["website_exists=false", "rejection_reason=missing_website"]
    return DiscoveryResult(candidate=candidate, score=0, status="rejected", reasons=["missing website"])


def _overpass_response_for_mode(
    *,
    mode: str,
    skip_overpass: bool,
    province: str,
    overpass_adapter: OverpassAdapter | None,
) -> OverpassDiscoveryResponse:
    if mode != "full":
        return OverpassDiscoveryResponse(status="skipped_non_full_mode")
    if skip_overpass:
        return OverpassDiscoveryResponse(status="skipped_cli")
    adapter = overpass_adapter or OverpassAdapter()
    return adapter.discover(province)


def _compute_overpass_domain_stats(
    seed_candidates: list[SourceCandidate],
    overpass_candidates: list[SourceCandidate],
) -> tuple[int, int]:
    seed_domains = {candidate.root_domain.lower() for candidate in seed_candidates if candidate.root_domain}
    overpass_domains = {candidate.root_domain.lower() for candidate in overpass_candidates if candidate.root_domain}
    duplicates = len(seed_domains & overpass_domains)
    new_domains = len(overpass_domains - seed_domains)
    return new_domains, duplicates


def _candidate_needs_live_aanbod(candidate: SourceCandidate) -> bool:
    if not candidate.website:
        return False
    return classify_aanbod_url(candidate.aanbod_url).status != "valid"


def _build_live_attempt(
    candidate: SourceCandidate,
    *,
    attempted: bool,
    success: bool,
    final_status: str,
    final_aanbod_url: str = "",
    detection_method: str = "",
    detection_score: int = 0,
    failure_stage: str = "unknown",
    failure_reason: str = "",
    http_status_homepage: int = 0,
    http_status_sitemap: int = 0,
    tested_urls_count: int = 0,
    best_candidate_url: str = "",
    best_candidate_reason: str = "",
    elapsed_ms: int = 0,
) -> LiveAanbodAttempt:
    return LiveAanbodAttempt(
        office_name=candidate.office_name,
        website=candidate.website,
        root_domain=candidate.root_domain,
        gemeente=candidate.gemeente,
        source_origin=candidate.source_origin,
        attempted=attempted,
        success=success,
        final_status=final_status,
        final_aanbod_url=final_aanbod_url,
        detection_method=detection_method,
        detection_score=detection_score,
        failure_stage=failure_stage,
        failure_reason=failure_reason,
        http_status_homepage=http_status_homepage,
        http_status_sitemap=http_status_sitemap,
        tested_urls_count=tested_urls_count,
        best_candidate_url=best_candidate_url,
        best_candidate_reason=best_candidate_reason,
        elapsed_ms=elapsed_ms,
    )


def run_discovery(
    *,
    province: str,
    mode: str,
    max_queries: int,
    max_sites: int,
    skip_overpass: bool = False,
    overpass_adapter: OverpassAdapter | None = None,
    live_aanbod: bool = False,
    max_live_sites: int = 0,
    website_fetcher: WebsiteFetcher | None = None,
    audit_aanbod: bool = False,
    max_audited_sites: int = 50,
    audit_confidence_threshold: int = 85,
) -> DiscoveryEngineOutput:
    normalized_province = normalize_province_name(province)
    run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_timestamp, run_dir = _create_run_dir(RUNS_DIR, run_timestamp)

    seed_candidates = [
        candidate
        for candidate in load_seed_candidates()
        if not normalized_province or candidate.provincie == normalized_province
    ]

    generated_queries = generate_queries_from_reference(
        path=DEFAULT_GEMEENTEN_REFERENCE_PATH,
        provincie=normalized_province,
    )[:max_queries]
    expected_gemeenten = load_expected_gemeenten(DEFAULT_GEMEENTEN_REFERENCE_PATH)
    aggregator_registry_rows = _load_aggregator_registry_rows(DEFAULT_AGGREGATOR_LEGAL_REGISTRY_PATH)

    overpass_response = _overpass_response_for_mode(
        mode=mode,
        skip_overpass=skip_overpass,
        province=normalized_province,
        overpass_adapter=overpass_adapter,
    )
    overpass_candidates = overpass_response.candidates
    overpass_new_domains_added, overpass_duplicates_vs_seed = _compute_overpass_domain_stats(
        seed_candidates,
        overpass_candidates,
    )
    overpass_response.new_domains_added = overpass_new_domains_added
    overpass_response.duplicates_vs_seed = overpass_duplicates_vs_seed

    overpass_without_website = [candidate for candidate in overpass_candidates if not candidate.website]
    resolver_output = resolve_websites(overpass_without_website, seed_candidates=seed_candidates)
    direct_rejections = [_mark_missing_website(candidate) for candidate in resolver_output.unresolved_candidates]
    candidates_with_website = (
        seed_candidates
        + [candidate for candidate in overpass_candidates if candidate.website]
        + resolver_output.resolved_candidates
    )
    limited_candidates = candidates_with_website[:max_sites]
    live_attempts: list[LiveAanbodAttempt] = []
    audit_attempts: list[AanbodAuditAttempt] = []
    existing_valid_aanbod_kept = sum(
        1 for candidate in limited_candidates if classify_aanbod_url(candidate.aanbod_url).status == "valid"
    )
    new_valid_aanbod_found = 0
    new_suspect_aanbod_found = 0
    live_attempts_used = 0
    live_fetcher = website_fetcher
    owns_fetcher = False
    if live_aanbod and max_live_sites > 0 and live_fetcher is None:
        live_fetcher = WebsiteFetcher()
        owns_fetcher = True

    if live_aanbod:
        for candidate in limited_candidates:
            if not candidate.website:
                live_attempts.append(_build_live_attempt(candidate, attempted=False, success=False, final_status="skipped_no_website"))
                continue
            if classify_aanbod_url(candidate.aanbod_url).status == "valid":
                live_attempts.append(
                    _build_live_attempt(
                        candidate,
                        attempted=False,
                        success=False,
                        final_status="skipped_existing_valid",
                        final_aanbod_url=candidate.aanbod_url,
                        detection_method=candidate.aanbod_detection_method,
                        detection_score=candidate.aanbod_detection_score,
                        best_candidate_url=candidate.aanbod_url,
                        best_candidate_reason=candidate.aanbod_validation_reason,
                    )
                )
                continue
            if max_live_sites <= 0 or live_attempts_used >= max_live_sites or live_fetcher is None:
                continue
            live_result = detect_live_aanbod_url(candidate, live_fetcher)
            live_attempts_used += 1
            before_status = classify_aanbod_url(candidate.aanbod_url).status
            apply_aanbod_classification(candidate, live_result.classification)
            final_status = live_result.classification.status
            if not live_result.succeeded and live_result.failure_stage == "homepage_fetch":
                final_status = "failed_fetch"
            if before_status != "valid" and candidate.aanbod_url_quality == "valid":
                new_valid_aanbod_found += 1
            elif before_status != "valid" and candidate.aanbod_url_quality == "suspect":
                new_suspect_aanbod_found += 1
            if live_result.failure_reason:
                candidate.review_reason = "; ".join(
                    part
                    for part in (candidate.review_reason, f"live aanbod: {live_result.failure_reason}")
                    if part
                )
            live_attempts.append(
                _build_live_attempt(
                    candidate,
                    attempted=live_result.attempted,
                    success=live_result.succeeded,
                    final_status=final_status,
                    final_aanbod_url=live_result.classification.url if final_status in {"valid", "suspect"} else "",
                    detection_method=live_result.classification.detection_method,
                    detection_score=live_result.classification.score,
                    failure_stage=live_result.failure_stage,
                    failure_reason=live_result.failure_reason,
                    http_status_homepage=live_result.http_status_homepage,
                    http_status_sitemap=live_result.http_status_sitemap,
                    tested_urls_count=live_result.tested_urls_count,
                    best_candidate_url=live_result.best_candidate_url,
                    best_candidate_reason=live_result.best_candidate_reason,
                    elapsed_ms=live_result.elapsed_ms,
                )
            )

    if audit_aanbod:
        auditor = AanbodAuditor(confidence_threshold=audit_confidence_threshold)
        audit_attempts = auditor.audit_candidates(
            limited_candidates,
            max_audited_sites=max_audited_sites,
        )

    analyzed_results = [_enrich_candidate(candidate) for candidate in limited_candidates]
    if owns_fetcher and live_fetcher is not None:
        live_fetcher.close()

    processed_results = analyzed_results + direct_rejections
    deduped_candidates = dedupe_candidates([result.candidate for result in processed_results])
    deduped_candidates_count = len(processed_results) - len(deduped_candidates)
    skipped_candidates_count = max(0, len(candidates_with_website) - len(limited_candidates))

    discovered_sources = [candidate for candidate in deduped_candidates if candidate.status != "rejected"]
    rejected_candidates = [candidate for candidate in deduped_candidates if candidate.status == "rejected"]

    candidate_rows = [_candidate_to_row(result.candidate) for result in processed_results]
    discovered_rows = [_candidate_to_row(candidate) for candidate in discovered_sources]
    rejected_rows = [_candidate_to_row(candidate) for candidate in rejected_candidates]
    query_rows = [_query_to_row(query) for query in generated_queries]
    live_attempt_rows = [_live_attempt_to_row(attempt) for attempt in live_attempts]
    audit_attempt_rows = [_audit_attempt_to_row(attempt) for attempt in audit_attempts]
    source_master_rows = build_source_master_rows(deduped_candidates, run_timestamp=run_timestamp)

    live_sites_attempted = sum(1 for attempt in live_attempts if attempt.attempted)
    live_sites_success = sum(1 for attempt in live_attempts if attempt.attempted and attempt.final_status in {"valid", "suspect"})
    live_sites_failed = live_sites_attempted - live_sites_success
    audited_sites_count = len(audit_attempts)
    browser_audit_valid_found = sum(1 for attempt in audit_attempts if attempt.final_status == "valid")
    browser_audit_suspect_found = sum(1 for attempt in audit_attempts if attempt.final_status == "suspect")
    browser_audit_missing_or_failed = sum(1 for attempt in audit_attempts if attempt.final_status in {"missing", "failed_fetch", "rejected"})
    browser_audit_unique_valid_domains = len(
        {(attempt.root_domain or "").lower() for attempt in audit_attempts if attempt.final_status == "valid" and not attempt.is_duplicate_audit_result}
    )
    browser_audit_unique_valid_urls = len(
        {attempt.final_aanbod_url.rstrip("/").lower() for attempt in audit_attempts if attempt.final_status == "valid" and attempt.final_aanbod_url and not attempt.is_duplicate_audit_result}
    )
    browser_audit_duplicate_valid_rows = sum(1 for attempt in audit_attempts if attempt.final_status == "valid" and attempt.is_duplicate_audit_result)

    fieldnames = [
        "office_name",
        "website",
        "root_domain",
        "raw_place",
        "normalized_place",
        "gemeente",
        "plaats",
        "place_status",
        "place_review_reason",
        "provincie",
        "aanbod_url",
        "aanbod_url_quality",
        "aanbod_url_type",
        "aanbod_detection_method",
        "aanbod_detection_score",
        "aanbod_validation_reason",
        "confidence",
        "needs_review",
        "source_adapter",
        "source_origin",
        "score",
        "status",
        "review_reason",
        "rejection_reason",
        "notes",
        "osm_type",
        "osm_id",
        "osm_website",
        "osm_contact_website",
        "osm_city",
        "osm_postcode",
        "osm_phone",
        "osm_contact_phone",
        "osm_email",
        "osm_contact_email",
        "osm_lat",
        "osm_lon",
        "evidence",
    ]

    _write_csv(run_dir / "candidate_domains.csv", candidate_rows, fieldnames)
    _write_csv(run_dir / "discovered_sources.csv", discovered_rows, fieldnames)
    _write_csv(run_dir / "rejected_candidates.csv", rejected_rows, fieldnames)
    _write_csv(
        run_dir / "generated_queries.csv",
        query_rows,
        ["gemeente", "provincie", "template", "query"],
    )
    _write_csv(
        run_dir / "live_aanbod_attempts.csv",
        live_attempt_rows,
        [
            "office_name",
            "website",
            "root_domain",
            "gemeente",
            "source_origin",
            "attempted",
            "success",
            "final_status",
            "final_aanbod_url",
            "detection_method",
            "detection_score",
            "failure_stage",
            "failure_reason",
            "http_status_homepage",
            "http_status_sitemap",
            "tested_urls_count",
            "best_candidate_url",
            "best_candidate_reason",
            "elapsed_ms",
        ],
    )
    _write_csv(
        run_dir / "aanbod_audit_results.csv",
        audit_attempt_rows,
        [
            "office_name",
            "website",
            "root_domain",
            "gemeente",
            "final_status",
            "final_aanbod_url",
            "confidence",
            "detection_method",
            "homepage_status",
            "homepage_title",
            "candidates_found_count",
            "candidates_tested_count",
            "best_candidate_url",
            "final_page_type",
            "residential_signals_count",
            "residential_signals_found",
            "commercial_signals_count",
            "commercial_signals_found",
            "page_quality_reason",
            "commercial_hard_block",
            "commercial_block_reason",
            "is_duplicate_audit_result",
            "listing_signals_count",
            "listing_signals_found",
            "rejection_reason",
            "elapsed_ms",
        ],
    )
    _write_csv(
        run_dir / "manual_website_review.csv",
        resolver_output.manual_review_rows,
        _manual_website_review_fieldnames(),
    )
    write_source_master(run_dir / "makelaar_sources_master.csv", source_master_rows)

    report_text = render_discovery_run_report(
        province=normalized_province,
        run_timestamp=run_timestamp,
        seed_count=len(seed_candidates),
        generated_queries=generated_queries,
        overpass_status=overpass_response.status,
        analyzed_results=processed_results,
        overpass_candidates=overpass_candidates,
        discovered_sources=discovered_sources,
        rejected_candidates=rejected_candidates,
        expected_gemeenten=expected_gemeenten,
        deduped_candidates_count=deduped_candidates_count,
        skipped_candidates_count=skipped_candidates_count,
        external_candidates_found=len(overpass_candidates),
        external_discovery_enabled=mode == "full" and not skip_overpass,
        overpass_raw_candidates=overpass_response.raw_candidates,
        overpass_candidates_with_website=overpass_response.candidates_with_website,
        overpass_candidates_without_website=overpass_response.candidates_without_website,
        overpass_new_domains_added=overpass_response.new_domains_added,
        overpass_duplicates_vs_seed=overpass_response.duplicates_vs_seed,
        overpass_errors=overpass_response.errors,
        live_aanbod_enabled=live_aanbod,
        live_sites_attempted=live_sites_attempted,
        live_sites_success=live_sites_success,
        live_sites_failed=live_sites_failed,
        existing_valid_aanbod_kept=existing_valid_aanbod_kept,
        new_valid_aanbod_found=new_valid_aanbod_found,
        new_suspect_aanbod_found=new_suspect_aanbod_found,
        live_attempts=live_attempts,
        audit_aanbod_enabled=audit_aanbod,
        audited_sites_count=audited_sites_count,
        browser_audit_valid_found=browser_audit_valid_found,
        browser_audit_suspect_found=browser_audit_suspect_found,
        browser_audit_missing_or_failed=browser_audit_missing_or_failed,
        browser_audit_unique_valid_domains=browser_audit_unique_valid_domains,
        browser_audit_unique_valid_urls=browser_audit_unique_valid_urls,
        browser_audit_duplicate_valid_rows=browser_audit_duplicate_valid_rows,
        valid_aanbod_after_audit=sum(1 for result in processed_results if result.candidate.aanbod_url_quality == "valid"),
        missing_aanbod_after_audit=sum(1 for result in processed_results if result.candidate.aanbod_url_quality == "missing"),
        audit_attempts=audit_attempts,
        overpass_cache_used=overpass_response.cache_used,
        overpass_cache_timestamp=overpass_response.cache_timestamp,
        overpass_source_label=overpass_response.source_label,
        source_master_rows=source_master_rows,
        missing_website_review_count=len(resolver_output.manual_review_rows),
        website_resolver_resolved_count=len(resolver_output.resolved_candidates),
        website_resolver_unresolved_count=len(resolver_output.unresolved_candidates),
        aggregator_registry_rows=aggregator_registry_rows,
    )
    report_path = run_dir / "discovery_run_report.md"
    write_discovery_run_report(report_path, report_text)

    _copy_to_latest(
        run_dir,
        LATEST_DIR,
        [
            "candidate_domains.csv",
            "discovered_sources.csv",
            "rejected_candidates.csv",
            "generated_queries.csv",
            "live_aanbod_attempts.csv",
            "aanbod_audit_results.csv",
            "manual_website_review.csv",
            "makelaar_sources_master.csv",
            "discovery_run_report.md",
        ],
    )

    return DiscoveryEngineOutput(
        run_timestamp=run_timestamp,
        run_dir=run_dir,
        latest_dir=LATEST_DIR,
        report_path=report_path,
        overpass_status=overpass_response.status,
        seed_count=len(seed_candidates),
        generated_queries_count=len(generated_queries),
        analyzed_candidates_count=len(processed_results) + skipped_candidates_count,
        discovered_sources_count=len(discovered_sources),
        rejected_candidates_count=len(rejected_candidates),
        deduped_candidates_count=deduped_candidates_count,
        skipped_candidates_count=skipped_candidates_count,
        external_candidates_found=len(overpass_candidates),
        external_discovery_enabled=mode == "full" and not skip_overpass,
        overpass_raw_candidates=overpass_response.raw_candidates,
        overpass_candidates_with_website=overpass_response.candidates_with_website,
        overpass_candidates_without_website=overpass_response.candidates_without_website,
        overpass_new_domains_added=overpass_response.new_domains_added,
        overpass_duplicates_vs_seed=overpass_response.duplicates_vs_seed,
        live_aanbod_enabled=live_aanbod,
        live_sites_attempted=live_sites_attempted,
        live_sites_success=live_sites_success,
        live_sites_failed=live_sites_failed,
        existing_valid_aanbod_kept=existing_valid_aanbod_kept,
        new_valid_aanbod_found=new_valid_aanbod_found,
        new_suspect_aanbod_found=new_suspect_aanbod_found,
        still_missing_aanbod=sum(1 for candidate in discovered_sources if candidate.aanbod_url_quality == "missing"),
    )
