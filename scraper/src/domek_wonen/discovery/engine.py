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
from .query_generator import generate_queries_from_reference
from .reporter import load_expected_gemeenten, render_discovery_run_report, write_discovery_run_report
from .scorer import score_candidate
from .search_api_adapter import SearchApiAdapter
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
    search_api_status: str
    seed_count: int
    generated_queries_count: int
    analyzed_candidates_count: int
    discovered_sources_count: int
    rejected_candidates_count: int
    deduped_candidates_count: int
    skipped_candidates_count: int
    external_candidates_found: int
    external_discovery_enabled: bool


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
        "gemeente": candidate.gemeente,
        "plaats": candidate.plaats,
        "provincie": candidate.provincie,
        "aanbod_url": candidate.aanbod_url,
        "aanbod_url_quality": candidate.aanbod_url_quality,
        "confidence": f"{candidate.confidence:.2f}",
        "needs_review": "true" if candidate.needs_review else "false",
        "source_adapter": candidate.source_adapter,
        "score": str(candidate.score),
        "status": candidate.status,
        "review_reason": candidate.review_reason,
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
        reasons.append("needs_review=true from seed")
    reasons.append(aanbod_classification.reason)

    candidate.aanbod_url_quality = aanbod_classification.status if aanbod_classification.status != "rejected" else "suspect"
    candidate.evidence = [item for item in evidence if item]
    candidate.review_reason = "; ".join(dict.fromkeys(reason for reason in reasons if reason))

    score_result = score_candidate(candidate)
    candidate.score = score_result.score
    candidate.status = score_result.status
    return DiscoveryResult(candidate=candidate, score=score_result.score, status=score_result.status, reasons=score_result.reasons)


def run_discovery(
    *,
    province: str,
    mode: str,
    max_queries: int,
    max_sites: int,
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

    search_api_adapter = SearchApiAdapter()
    search_response = search_api_adapter.search(generated_queries, max_sites=max_sites)
    external_candidates = search_response.results
    external_discovery_enabled = search_response.status != "disabled_missing_credentials"

    limited_candidates = seed_candidates[:max_sites]
    analyzed_results = [_enrich_candidate(candidate) for candidate in limited_candidates]
    deduped_candidates = dedupe_candidates([result.candidate for result in analyzed_results])
    deduped_candidates_count = len(analyzed_results) - len(deduped_candidates)
    skipped_candidates_count = 0

    discovered_sources = [candidate for candidate in deduped_candidates if candidate.status != "rejected"]
    rejected_candidates = [candidate for candidate in deduped_candidates if candidate.status == "rejected"]

    candidate_rows = [_candidate_to_row(result.candidate) for result in analyzed_results]
    discovered_rows = [_candidate_to_row(candidate) for candidate in discovered_sources]
    rejected_rows = [_candidate_to_row(candidate) for candidate in rejected_candidates]
    query_rows = [_query_to_row(query) for query in generated_queries]

    _write_csv(
        run_dir / "candidate_domains.csv",
        candidate_rows,
        [
            "office_name",
            "website",
            "root_domain",
            "gemeente",
            "plaats",
            "provincie",
            "aanbod_url",
            "aanbod_url_quality",
            "confidence",
            "needs_review",
            "source_adapter",
            "score",
            "status",
            "review_reason",
            "evidence",
        ],
    )
    _write_csv(
        run_dir / "discovered_sources.csv",
        discovered_rows,
        [
            "office_name",
            "website",
            "root_domain",
            "gemeente",
            "plaats",
            "provincie",
            "aanbod_url",
            "aanbod_url_quality",
            "confidence",
            "needs_review",
            "source_adapter",
            "score",
            "status",
            "review_reason",
            "evidence",
        ],
    )
    _write_csv(
        run_dir / "rejected_candidates.csv",
        rejected_rows,
        [
            "office_name",
            "website",
            "root_domain",
            "gemeente",
            "plaats",
            "provincie",
            "aanbod_url",
            "aanbod_url_quality",
            "confidence",
            "needs_review",
            "source_adapter",
            "score",
            "status",
            "review_reason",
            "evidence",
        ],
    )
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
        search_api_status=search_response.status,
        analyzed_results=analyzed_results,
        discovered_sources=discovered_sources,
        rejected_candidates=rejected_candidates,
        expected_gemeenten=expected_gemeenten,
        deduped_candidates_count=deduped_candidates_count,
        skipped_candidates_count=skipped_candidates_count,
        external_candidates_found=len(external_candidates),
        external_discovery_enabled=external_discovery_enabled,
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
        search_api_status=search_response.status,
        seed_count=len(seed_candidates),
        generated_queries_count=len(generated_queries),
        analyzed_candidates_count=len(analyzed_results),
        discovered_sources_count=len(discovered_sources),
        rejected_candidates_count=len(rejected_candidates),
        deduped_candidates_count=deduped_candidates_count,
        skipped_candidates_count=skipped_candidates_count,
        external_candidates_found=len(external_candidates),
        external_discovery_enabled=external_discovery_enabled,
    )
