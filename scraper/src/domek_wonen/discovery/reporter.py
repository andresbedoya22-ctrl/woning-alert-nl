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
    covered = {candidate.gemeente.strip() for candidate in discovered_sources if candidate.gemeente.strip()}
    return [gemeente for gemeente in expected_gemeenten if gemeente not in covered]


def split_missing_expected_gemeenten(
    expected_gemeenten: list[str],
    discovered_sources: list[SourceCandidate],
    rejected_candidates: list[SourceCandidate],
) -> dict[str, list[str]]:
    accepted = {candidate.gemeente.strip() for candidate in discovered_sources if candidate.gemeente.strip()}
    all_candidates = {
        candidate.gemeente.strip()
        for candidate in discovered_sources + rejected_candidates
        if candidate.gemeente.strip() and candidate.gemeente.strip() != "(unknown)"
    }
    missing_expected_with_no_candidates = [
        gemeente for gemeente in expected_gemeenten if gemeente not in accepted and gemeente not in all_candidates
    ]
    expected_with_candidates_but_no_accepted_sources = [
        gemeente for gemeente in expected_gemeenten if gemeente not in accepted and gemeente in all_candidates
    ]
    return {
        "missing_expected_with_no_candidates": missing_expected_with_no_candidates,
        "expected_with_candidates_but_no_accepted_sources": expected_with_candidates_but_no_accepted_sources,
    }


def build_overpass_place_normalization_summary(
    candidates: list[SourceCandidate],
) -> list[dict[str, int | str]]:
    by_status: Counter[str] = Counter()
    for candidate in candidates:
        if candidate.source_adapter != "overpass":
            continue
        by_status[candidate.place_status or "missing"] += 1
    rows = [{"place_status": status, "count": count} for status, count in sorted(by_status.items())]
    return rows or [{"place_status": "none", "count": 0}]


def build_overpass_unmapped_places(candidates: list[SourceCandidate]) -> list[dict[str, int | str]]:
    counts: Counter[str] = Counter()
    for candidate in candidates:
        if candidate.source_adapter != "overpass":
            continue
        if candidate.place_status == "needs_review":
            counts[candidate.raw_place or "(empty)"] += 1
    return [
        {"raw_place": raw_place, "count": count}
        for raw_place, count in sorted(counts.items(), key=lambda item: (item[0].lower(), -item[1]))
    ]


def build_query_target_rows(
    expected_gemeenten: list[str],
    discovered_sources: list[SourceCandidate],
    coverage_rows: list[dict[str, int | str]],
) -> list[dict[str, int | str]]:
    total_by_gemeente = {str(row["gemeente"]): int(row["total"]) for row in coverage_rows}
    valid_by_gemeente = {str(row["gemeente"]): int(row["valid"]) for row in coverage_rows}
    discovered_by_gemeente = Counter(
        candidate.gemeente.strip() for candidate in discovered_sources if candidate.gemeente.strip()
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


def overpass_status_explanation(overpass_status: str) -> str:
    if overpass_status == "ok":
        return "Overpass external discovery completed using the primary mirror."
    if overpass_status == "ok_fallback":
        return "Overpass primary mirror failed; external discovery completed using the fallback mirror."
    if overpass_status == "failed":
        return "Both Overpass mirrors failed; the engine continued with seed-only processing."
    if overpass_status == "skipped_cli":
        return "Overpass discovery was skipped because --skip-overpass was provided."
    if overpass_status == "skipped_non_full_mode":
        return "Overpass discovery only runs in full mode."
    return "Overpass status is unknown; treat this run as seed-only unless proven otherwise."


def next_recommended_actions(
    coverage_rows: list[dict[str, int | str]],
    missing_summary: dict[str, list[str]],
    overpass_status: str,
) -> list[str]:
    actions: list[str] = []
    weak_rows = sorted(coverage_rows, key=lambda item: int(item["weak_score"]), reverse=True)
    if overpass_status == "failed":
        actions.append("Retry the same full run later to recover external discovery from the Overpass mirrors.")
    zero_candidates = missing_summary["missing_expected_with_no_candidates"]
    rejected_only = missing_summary["expected_with_candidates_but_no_accepted_sources"]
    if zero_candidates:
        preview = ", ".join(zero_candidates[:10])
        actions.append(f"Investigate expected gemeenten with zero discovered sources after Overpass: {preview}.")
    if rejected_only:
        preview = ", ".join(rejected_only[:10])
        actions.append(f"Review rejected-only gemeenten where candidates were found but none were accepted: {preview}.")
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
    overpass_status: str,
    analyzed_results: list[DiscoveryResult],
    overpass_candidates: list[SourceCandidate],
    discovered_sources: list[SourceCandidate],
    rejected_candidates: list[SourceCandidate],
    expected_gemeenten: list[str],
    deduped_candidates_count: int,
    skipped_candidates_count: int,
    external_candidates_found: int,
    external_discovery_enabled: bool,
    overpass_raw_candidates: int,
    overpass_candidates_with_website: int,
    overpass_candidates_without_website: int,
    overpass_new_domains_added: int,
    overpass_duplicates_vs_seed: int,
    overpass_errors: list[str],
) -> str:
    analyzed_count = len(analyzed_results) + skipped_candidates_count
    valid_aanbod_count = sum(1 for result in analyzed_results if result.candidate.aanbod_url_quality == "valid")
    suspect_count = sum(1 for result in analyzed_results if result.candidate.aanbod_url_quality == "suspect")
    missing_count = sum(1 for result in analyzed_results if result.candidate.aanbod_url_quality == "missing")
    rejected_count = sum(1 for result in analyzed_results if result.status == "rejected")

    coverage_rows = build_coverage_rows(discovered_sources + rejected_candidates)
    missing_summary = split_missing_expected_gemeenten(expected_gemeenten, discovered_sources, rejected_candidates)
    weak_rows = sorted(coverage_rows, key=lambda item: int(item["weak_score"]), reverse=True)[:15]
    query_targets = build_query_target_rows(expected_gemeenten, discovered_sources, coverage_rows)[:15]
    actions = next_recommended_actions(coverage_rows, missing_summary, overpass_status)
    status_explanation = overpass_status_explanation(overpass_status)
    normalization_rows = build_overpass_place_normalization_summary(overpass_candidates)
    unmapped_place_rows = build_overpass_unmapped_places(overpass_candidates)

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

    rejected_only_lines = [
        f"- {gemeente}" for gemeente in missing_summary["expected_with_candidates_but_no_accepted_sources"]
    ] or ["- None"]
    zero_candidate_lines = [f"- {gemeente}" for gemeente in missing_summary["missing_expected_with_no_candidates"]] or [
        "- None"
    ]
    normalization_lines = [
        f"- {row['place_status']}: {row['count']}" for row in normalization_rows
    ] or ["- none: 0"]
    unmapped_place_lines = [
        f"- {row['raw_place']}: {row['count']}" for row in unmapped_place_rows
    ] or ["- None"]
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
    error_lines = [f"- {error}" for error in overpass_errors] or ["- None"]

    return "\n".join(
        [
            "# Discovery Run Report",
            "",
            "## Summary",
            f"- Province: {province}",
            f"- Run timestamp: {run_timestamp}",
            f"- Seed count: {seed_count}",
            f"- Generated queries count: {len(generated_queries)}",
            f"- Free external discovery enabled: {'true' if external_discovery_enabled else 'false'}",
            f"- Overpass status: {overpass_status}",
            f"- Overpass raw candidates: {overpass_raw_candidates}",
            f"- Overpass candidates with website: {overpass_candidates_with_website}",
            f"- Overpass candidates without website: {overpass_candidates_without_website}",
            f"- Overpass new domains added: {overpass_new_domains_added}",
            f"- Overpass duplicates vs seed: {overpass_duplicates_vs_seed}",
            f"- External candidates found: {external_candidates_found}",
            f"- Analyzed candidates count: {analyzed_count}",
            f"- Valid aanbod_url after Overpass: {valid_aanbod_count}",
            f"- Suspect after Overpass: {suspect_count}",
            f"- Missing aanbod_url after Overpass: {missing_count}",
            f"- Rejected count: {rejected_count}",
            f"- Discovered sources count: {len(discovered_sources)}",
            f"- Rejected candidates count: {len(rejected_candidates)}",
            f"- Deduped candidates count: {deduped_candidates_count}",
            f"- Skipped candidates count: {skipped_candidates_count}",
            f"- Reconciliation check: analyzed={analyzed_count}, discovered+rejected+deduped+skipped={reconciled_total}",
            "",
            "## Overpass Status Explanation",
            status_explanation,
            "",
            "## Overpass Errors",
            *error_lines,
            "",
            "## Overpass Place Normalization Summary",
            *normalization_lines,
            "",
            "## Overpass unmapped places",
            *unmapped_place_lines,
            "",
            "## Coverage By Gemeente",
            *coverage_lines,
            "",
            "## Missing Expected Gemeenten After Overpass",
            "### Expected gemeenten with rejected-only candidates",
            *rejected_only_lines,
            "",
            "### Expected gemeenten still with zero candidates",
            *zero_candidate_lines,
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
            "## Next Recommended Actions",
            *action_lines,
            "",
        ]
    )


def write_discovery_run_report(path: Path, report_text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report_text, encoding="utf-8")
