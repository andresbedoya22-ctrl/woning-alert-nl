from __future__ import annotations

import csv
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .aanbod_finder import classify_aanbod_url, suggest_common_aanbod_paths
from .config import DEFAULT_GEMEENTEN_REFERENCE_PATH, DISCOVERY_BASE_DIR
from .dedupe import dedupe_candidates
from .models import DiscoveryResult, GeneratedQuery, SourceCandidate
from .overpass_adapter import OverpassAdapter, OverpassDiscoveryResponse
from .query_generator import generate_queries_from_reference
from .reporter import load_expected_gemeenten, render_discovery_run_report, write_discovery_run_report
from .scorer import score_candidate
from .seed_adapter import load_seed_candidates
from .website_analyzer import analyze_candidate_website


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


def _enrich_candidate(candidate: SourceCandidate) -> DiscoveryResult:
    website_analysis = analyze_candidate_website(candidate)
    aanbod_classification = classify_aanbod_url(candidate.aanbod_url)

    evidence: list[str] = []
    evidence.append(f"website_exists={str(website_analysis.website_exists).lower()}")
    if website_analysis.makelaar_signals:
        evidence.append("makelaar_signals=" + ",".join(website_analysis.makelaar_signals))
    evidence.append(f"aanbod_url_status={aanbod_classification.status}")
    evidence.append(f"aanbod_url_reason={aanbod_classification.reason}")

    if not candidate.aanbod_url and candidate.website:
        suggestions = suggest_common_aanbod_paths(candidate.website)
        if suggestions:
            evidence.append("suggested_aanbod_paths=" + ",".join(suggestions[:3]))

    reasons = [candidate.review_reason] if candidate.review_reason else []
    if candidate.needs_review and not reasons:
        reasons.append("needs_review=true from source")
    reasons.append(aanbod_classification.reason)

    candidate.aanbod_url_quality = aanbod_classification.status if aanbod_classification.status != "rejected" else "suspect"
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


def run_discovery(
    *,
    province: str,
    mode: str,
    max_queries: int,
    max_sites: int,
    skip_overpass: bool = False,
    overpass_adapter: OverpassAdapter | None = None,
) -> DiscoveryEngineOutput:
    normalized_province = normalize_province_name(province)
    run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = RUNS_DIR / run_timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

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

    direct_rejections = [_mark_missing_website(candidate) for candidate in overpass_candidates if not candidate.website]
    candidates_with_website = seed_candidates + [candidate for candidate in overpass_candidates if candidate.website]
    limited_candidates = candidates_with_website[:max_sites]
    analyzed_results = [_enrich_candidate(candidate) for candidate in limited_candidates]

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
    )
