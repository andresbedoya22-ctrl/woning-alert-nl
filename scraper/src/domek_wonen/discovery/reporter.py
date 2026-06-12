from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from .models import DiscoveryResult, GeneratedQuery, SourceCandidate


def load_expected_gemeenten(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(handle)
        return [row["gemeente"].strip() for row in rows if (row.get("gemeente") or "").strip()]


def build_coverage_rows(candidates: list[SourceCandidate]) -> list[dict[str, int | str]]:
    by_gemeente: dict[str, Counter[str]] = {}
    for candidate in candidates:
        gemeente = candidate.gemeente or "(unknown)"
        counter = by_gemeente.setdefault(gemeente, Counter())
        counter["total"] += 1
        counter[candidate.status or "missing"] += 1
        if candidate.aanbod_url_quality == "valid":
            counter["valid_aanbod"] += 1

    rows: list[dict[str, int | str]] = []
    for gemeente, counter in by_gemeente.items():
        weak_score = (
            counter["missing"] * 3
            + counter["suspect"] * 2
            + counter["rejected"] * 4
            + (1 if counter["valid_aanbod"] == 0 else 0) * 5
        )
        rows.append(
            {
                "gemeente": gemeente,
                "total": counter["total"],
                "valid": counter["valid"],
                "suspect": counter["suspect"],
                "missing": counter["missing"],
                "rejected": counter["rejected"],
                "valid_aanbod": counter["valid_aanbod"],
                "weak_score": weak_score,
            }
        )
    return sorted(rows, key=lambda item: (str(item["gemeente"]).lower(), -int(item["total"])))


def compute_missing_expected_gemeenten(
    expected_gemeenten: list[str],
    discovered_sources: list[SourceCandidate],
) -> list[str]:
    covered = {
        candidate.gemeente.strip()
        for candidate in discovered_sources
        if candidate.gemeente.strip()
    }
    return [gemeente for gemeente in expected_gemeenten if gemeente not in covered]


def build_query_target_rows(
    expected_gemeenten: list[str],
    discovered_sources: list[SourceCandidate],
    coverage_rows: list[dict[str, int | str]],
) -> list[dict[str, int | str]]:
    total_by_gemeente = {str(row["gemeente"]): int(row["total"]) for row in coverage_rows}
    valid_by_gemeente = {str(row["gemeente"]): int(row["valid"]) for row in coverage_rows}
    discovered_by_gemeente = Counter(
        candidate.gemeente.strip()
        for candidate in discovered_sources
        if candidate.gemeente.strip()
    )

    targets: list[dict[str, int | str]] = []
    for gemeente in expected_gemeenten:
        discovered_count = discovered_by_gemeente.get(gemeente, 0)
        total_count = total_by_gemeente.get(gemeente, 0)
        valid_count = valid_by_gemeente.get(gemeente, 0)
        priority = 100 - (discovered_count * 20) - (valid_count * 10) - min(total_count, 5)
        if discovered_count == 0:
            priority += 50
        targets.append(
            {
                "gemeente": gemeente,
                "discovered_count": discovered_count,
                "total_count": total_count,
                "valid_count": valid_count,
                "priority": priority,
            }
        )
    return sorted(targets, key=lambda item: (-int(item["priority"]), str(item["gemeente"]).lower()))


def search_api_status_explanation(search_api_status: str) -> str:
    if search_api_status == "disabled_missing_credentials":
        return (
            "External discovery was not executed because GOOGLE_CUSTOM_SEARCH_API_KEY or "
            "GOOGLE_CUSTOM_SEARCH_ENGINE_ID is missing. This run only analyzed local seed data."
        )
    if search_api_status == "configured_future_google_custom_search":
        return (
            "Credentials are configured, but external Google Custom Search calls are still stubbed in v1. "
            "No real external search results were used in this run."
        )
    return "Search API status is unknown; treat this run as local-only unless proven otherwise."


def next_recommended_actions(
    coverage_rows: list[dict[str, int | str]],
    missing_expected_gemeenten: list[str],
    search_api_status: str,
) -> list[str]:
    actions: list[str] = []
    weak_rows = sorted(coverage_rows, key=lambda item: int(item["weak_score"]), reverse=True)
    if search_api_status == "disabled_missing_credentials":
        actions.append(
            "Set GOOGLE_CUSTOM_SEARCH_API_KEY and GOOGLE_CUSTOM_SEARCH_ENGINE_ID before the next run to unlock real external discovery."
        )
    if missing_expected_gemeenten:
        preview = ", ".join(missing_expected_gemeenten[:10])
        actions.append(f"Investigate expected gemeenten with zero discovered sources: {preview}.")
    if any(int(row["missing"]) > 0 for row in coverage_rows):
        actions.append("Review offices with missing aanbod_url and validate suggested common paths on official websites.")
    if any(int(row["suspect"]) > 0 for row in coverage_rows):
        actions.append("Manually verify suspect aanbod_url pages that look commercial or ambiguous.")
    if weak_rows:
        weakest = ", ".join(str(row["gemeente"]) for row in weak_rows[:5])
        actions.append(f"Prioritize weak gemeenten first: {weakest}.")
    return actions or ["No immediate follow-up actions generated."]


def render_discovery_run_report(
    *,
    province: str,
    run_timestamp: str,
    seed_count: int,
    generated_queries: list[GeneratedQuery],
    search_api_status: str,
    analyzed_results: list[DiscoveryResult],
    discovered_sources: list[SourceCandidate],
    rejected_candidates: list[SourceCandidate],
    expected_gemeenten: list[str],
    deduped_candidates_count: int,
    skipped_candidates_count: int,
    external_candidates_found: int,
    external_discovery_enabled: bool,
) -> str:
    analyzed_count = len(analyzed_results)
    valid_aanbod_count = sum(1 for result in analyzed_results if result.candidate.aanbod_url_quality == "valid")
    suspect_count = sum(1 for result in analyzed_results if result.candidate.aanbod_url_quality == "suspect")
    missing_count = sum(1 for result in analyzed_results if result.candidate.aanbod_url_quality == "missing")
    rejected_count = sum(1 for result in analyzed_results if result.status == "rejected")

    coverage_rows = build_coverage_rows(discovered_sources + rejected_candidates)
    missing_expected = compute_missing_expected_gemeenten(expected_gemeenten, discovered_sources)
    weak_rows = sorted(coverage_rows, key=lambda item: int(item["weak_score"]), reverse=True)[:15]
    query_targets = build_query_target_rows(expected_gemeenten, discovered_sources, coverage_rows)[:15]
    actions = next_recommended_actions(coverage_rows, missing_expected, search_api_status)
    status_explanation = search_api_status_explanation(search_api_status)

    reconciled_total = len(discovered_sources) + len(rejected_candidates) + deduped_candidates_count + skipped_candidates_count

    coverage_lines = [
        "| gemeente | total | valid | suspect | missing | rejected | valid_aanbod | weak_score |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in coverage_rows:
        coverage_lines.append(
            f"| {row['gemeente']} | {row['total']} | {row['valid']} | {row['suspect']} | "
            f"{row['missing']} | {row['rejected']} | {row['valid_aanbod']} | {row['weak_score']} |"
        )

    missing_lines = [f"- {gemeente}" for gemeente in missing_expected] or ["- None"]
    weak_lines = [
        f"- {row['gemeente']}: weak_score={row['weak_score']}, valid={row['valid']}, "
        f"suspect={row['suspect']}, missing={row['missing']}, rejected={row['rejected']}"
        for row in weak_rows
    ] or ["- None"]
    query_target_lines = [
        f"- {row['gemeente']}: priority={row['priority']}, discovered={row['discovered_count']}, "
        f"total={row['total_count']}, valid={row['valid_count']}"
        for row in query_targets
    ] or ["- None"]
    action_lines = [f"- {action}" for action in actions]

    return "\n".join(
        [
            "# Discovery Run Report",
            "",
            "## Summary",
            f"- Province: {province}",
            f"- Run timestamp: {run_timestamp}",
            f"- Seed count: {seed_count}",
            f"- Generated queries count: {len(generated_queries)}",
            f"- Search API status: {search_api_status}",
            f"- External discovery enabled: {'true' if external_discovery_enabled else 'false'}",
            f"- External candidates found: {external_candidates_found}",
            f"- Analyzed candidates count: {analyzed_count}",
            f"- Valid aanbod_url count: {valid_aanbod_count}",
            f"- Suspect count: {suspect_count}",
            f"- Missing count: {missing_count}",
            f"- Rejected count: {rejected_count}",
            f"- Discovered sources count: {len(discovered_sources)}",
            f"- Rejected candidates count: {len(rejected_candidates)}",
            f"- Deduped candidates count: {deduped_candidates_count}",
            f"- Skipped candidates count: {skipped_candidates_count}",
            f"- Reconciliation check: analyzed={analyzed_count}, discovered+rejected+deduped+skipped={reconciled_total}",
            "",
            "## Search API Status Explanation",
            status_explanation,
            "",
            "## Coverage By Gemeente",
            *coverage_lines,
            "",
            "## Missing Expected Gemeenten",
            *missing_lines,
            "",
            "## Deduplication Summary",
            f"- Unique sources after dedupe: {len(discovered_sources) + len(rejected_candidates)}",
            f"- Deduped candidates removed from final outputs: {deduped_candidates_count}",
            f"- Skipped candidates during analysis: {skipped_candidates_count}",
            "",
            "## Top 15 Gemeenten Still Weak",
            *weak_lines,
            "",
            "## Top Recommended Query Targets",
            *query_target_lines,
            "",
            "## Next Step To Enable Real External Discovery",
            "- Add GOOGLE_CUSTOM_SEARCH_API_KEY and GOOGLE_CUSTOM_SEARCH_ENGINE_ID to the environment.",
            "- Implement live Google Custom Search JSON API calls in search_api_adapter.py.",
            "- Keep no Google result page scraping and no Funda scraping.",
            "",
            "## Next Recommended Actions",
            *action_lines,
            "",
        ]
    )


def write_discovery_run_report(path: Path, report_text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report_text, encoding="utf-8")
