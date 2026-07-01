from __future__ import annotations

import csv
import time
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from domek_wonen.pilots.realworks_property_readiness import (
    RealworksPropertyReadinessResult,
    RealworksPropertyReadinessRow,
    run_realworks_property_readiness,
)


EXPECTED_NB_REALWORKS_AUDIT_ROWS = 65
REALWORKS_READY_STATUS = "ready_for_noord_brabant_realworks_audit"
REALWORKS_FAMILY = "realworks_public"
REALWORKS_VERIFIED = "verified"
FAMILY_DECISIONS = (
    "realworks_ready_for_nb_family_coverage",
    "realworks_partially_ready_with_exclusions",
    "realworks_needs_hardening_v2",
    "blocked_by_access_policy",
    "insufficient_successful_sources",
)
RAW_MARKERS = ("<html", "<script", "</", '{"', "{'", '"docs"', "window.__")
LONG_TEXT_LIMIT = 500
REQUIRED_INPUT_COLUMNS = (
    "source_id",
    "source_name",
    "domain",
    "accepted_aanbod_url",
    "coverage_city",
    "coverage_gemeente",
    "coverage_province",
    "aanbod_scope_status",
    "realworks_verification_status",
    "realworks_evidence_strength",
    "audit_input_status",
    "parser_family_candidate",
)
SUMMARY_COLUMNS = (
    "source_id",
    "source_name",
    "domain",
    "accepted_aanbod_url",
    "coverage_city",
    "coverage_gemeente",
    "aanbod_scope_status",
    "access_policy_status",
    "robots_listing_allowed",
    "listing_fetch_status",
    "listing_http_status",
    "parser_total",
    "parser_qa_clean",
    "parser_qa_review",
    "parser_qa_rejected",
    "detail_attempted",
    "detail_succeeded",
    "detail_failed",
    "readiness_rows_built",
    "export_ready",
    "export_review",
    "export_blocked",
    "active_inventory_eligible",
    "inactive_status_count",
    "non_residential_count",
    "no_current_listings",
    "top_warning",
    "validation_status",
    "validation_decision",
    "recommended_next_action",
)
MANUAL_VERIFICATION_COLUMNS = (
    "source_id",
    "domain",
    "address",
    "city",
    "price",
    "status",
    "accepted_aanbod_url",
    "canonical_url",
    "property_link",
    "export_readiness",
    "quality_status",
    "missing_key_fields",
    "warnings",
    "manual_check_result",
    "manual_check_notes",
)


class NoordBrabantRealworksAuditInputError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class NoordBrabantRealworksAuditSource:
    source_id: str
    source_name: str
    domain: str
    accepted_aanbod_url: str
    coverage_city: str
    coverage_gemeente: str
    coverage_province: str
    aanbod_scope_status: str
    realworks_verification_status: str
    realworks_evidence_strength: str
    audit_input_status: str
    parser_family_candidate: str


@dataclass(frozen=True, slots=True)
class NoordBrabantRealworksAuditMetrics:
    source_id: str
    source_name: str
    domain: str
    accepted_aanbod_url: str
    coverage_city: str
    coverage_gemeente: str
    aanbod_scope_status: str
    access_policy_status: str
    robots_listing_allowed: bool
    listing_fetch_status: str
    listing_http_status: str
    parser_total: int
    parser_qa_clean: int
    parser_qa_review: int
    parser_qa_rejected: int
    detail_attempted: int
    detail_succeeded: int
    detail_failed: int
    readiness_rows_built: int
    export_ready: int
    export_review: int
    export_blocked: int
    active_inventory_eligible: int
    inactive_status_count: int
    non_residential_count: int
    no_current_listings: bool
    top_warning: str
    warning_counts: tuple[tuple[str, int], ...]
    field_gap_counts: tuple[tuple[str, int], ...]
    failure_patterns: tuple[str, ...]
    validation_status: str
    validation_decision: str
    recommended_next_action: str


@dataclass(frozen=True, slots=True)
class NoordBrabantRealworksFamilyDecision:
    family_decision: str
    confidence: str
    reasons: tuple[str, ...]
    next_action: str
    source_exclusions: tuple[str, ...]
    hardening_targets: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NoordBrabantRealworksAggregateMetrics:
    input_sources: int
    sources_attempted: int
    sources_skipped: int
    sources_passed: int
    sources_passed_with_review_gaps: int
    sources_no_current_listings: int
    sources_blocked: int
    sources_fetch_failed: int
    sources_needing_hardening: int
    total_parser_rows: int
    total_qa_clean: int
    total_qa_review: int
    total_qa_rejected: int
    total_detail_attempted: int
    total_detail_succeeded: int
    total_detail_failed: int
    total_readiness_rows: int
    total_export_ready: int
    total_export_review: int
    total_export_blocked: int
    field_gap_counts: tuple[tuple[str, int], ...]
    warning_counts: tuple[tuple[str, int], ...]
    failure_pattern_counts: tuple[tuple[str, int], ...]
    runtime_budget_exhausted: bool


@dataclass(frozen=True, slots=True)
class NoordBrabantRealworksAuditResult:
    sources: tuple[NoordBrabantRealworksAuditSource, ...]
    metrics: tuple[NoordBrabantRealworksAuditMetrics, ...]
    readiness_results: tuple[RealworksPropertyReadinessResult, ...]
    aggregate_metrics: NoordBrabantRealworksAggregateMetrics
    family_decision: NoordBrabantRealworksFamilyDecision
    observed_at: datetime
    workbook_path: Path | None = None
    summary_csv_path: Path | None = None
    problem_sources_csv_path: Path | None = None
    warnings: tuple[str, ...] = ()


ReadinessRunner = Callable[..., RealworksPropertyReadinessResult]


def load_noord_brabant_realworks_audit_sources(
    input_csv: Path,
    *,
    expected_rows: int = EXPECTED_NB_REALWORKS_AUDIT_ROWS,
) -> tuple[NoordBrabantRealworksAuditSource, ...]:
    path = Path(input_csv)
    if not path.exists():
        raise NoordBrabantRealworksAuditInputError(f"missing input CSV: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        columns = tuple(reader.fieldnames or ())

    missing_columns = [column for column in REQUIRED_INPUT_COLUMNS if column not in columns]
    if missing_columns:
        raise NoordBrabantRealworksAuditInputError(f"missing required columns: {', '.join(missing_columns)}")
    if not rows:
        raise NoordBrabantRealworksAuditInputError("input CSV has no rows")
    if expected_rows is not None and len(rows) != expected_rows:
        raise NoordBrabantRealworksAuditInputError(f"expected {expected_rows} rows, got {len(rows)}")

    sources: list[NoordBrabantRealworksAuditSource] = []
    gate_counts = _input_gate_counts(rows)
    failing_gates = {key: value for key, value in gate_counts.items() if value}
    if failing_gates:
        details = "; ".join(f"{key}={value}" for key, value in sorted(failing_gates.items()))
        raise NoordBrabantRealworksAuditInputError(f"input hard gates failed: {details}")

    duplicate_counts = Counter(
        (_normalize_domain(row.get("domain")), _normalize_url(row.get("accepted_aanbod_url")))
        for row in rows
    )
    duplicates = [key for key, count in duplicate_counts.items() if count > 1]
    if duplicates:
        raise NoordBrabantRealworksAuditInputError(f"duplicate domain+accepted_aanbod_url rows: {len(duplicates)}")

    for index, row in enumerate(rows, start=2):
        source = _source_from_row(row)
        validation_error = _validate_source(source)
        if validation_error:
            raise NoordBrabantRealworksAuditInputError(f"row {index}: {validation_error}")
        sources.append(source)
    return tuple(sources)


def run_noord_brabant_realworks_audit(
    *,
    input_csv: Path,
    output_workbook: Path | None = None,
    output_summary: Path | None = None,
    output_problem_sources: Path | None = None,
    max_sources: int = EXPECTED_NB_REALWORKS_AUDIT_ROWS,
    max_listings_per_source: int = 15,
    max_detail_per_source: int = 10,
    timeout_seconds: float = 15.0,
    runtime_budget_seconds: float = 1800.0,
    observed_at: datetime | None = None,
    fetch_html: Callable[[str], str] | None = None,
    readiness_runner: ReadinessRunner = run_realworks_property_readiness,
) -> NoordBrabantRealworksAuditResult:
    observed = _to_utc(observed_at or datetime.now(UTC))
    sources = load_noord_brabant_realworks_audit_sources(input_csv)
    capped_sources = tuple(sources[: max(0, min(max_sources, len(sources)))])
    start = time.monotonic()
    budget_exhausted = False
    metrics: list[NoordBrabantRealworksAuditMetrics] = []
    readiness_results: list[RealworksPropertyReadinessResult] = []
    warnings: list[str] = []

    for source in capped_sources:
        if _runtime_exhausted(start, runtime_budget_seconds):
            budget_exhausted = True
            warnings.append("runtime_budget_exhausted")
            break
        try:
            readiness = readiness_runner(
                source_id=source.source_id,
                source_domain=source.domain,
                listing_url=source.accepted_aanbod_url,
                max_listing_fetches=max(0, max_listings_per_source),
                max_detail_fetches=max(0, max_detail_per_source),
                timeout_seconds=timeout_seconds,
                fetch_html=fetch_html,
                observed_at=observed,
            )
        except Exception as exc:
            warnings.append("source_runner_exception")
            readiness = _empty_readiness_result(source, ("source_runner_exception", type(exc).__name__))
        readiness_results.append(readiness)
        metrics.append(_metrics_for_source(source, readiness))
        warnings.extend(readiness.warnings)

    aggregate = aggregate_noord_brabant_realworks_metrics(
        input_sources=len(sources),
        attempted_sources=len(metrics),
        metrics=metrics,
        runtime_budget_exhausted=budget_exhausted,
    )
    decision = decide_noord_brabant_realworks_family(metrics, aggregate)
    result = NoordBrabantRealworksAuditResult(
        sources=sources,
        metrics=tuple(metrics),
        readiness_results=tuple(readiness_results),
        aggregate_metrics=aggregate,
        family_decision=decision,
        observed_at=observed,
        warnings=_dedupe(warnings),
    )
    workbook_path = write_noord_brabant_realworks_audit_workbook(result, output_workbook) if output_workbook else None
    summary_path = write_noord_brabant_realworks_summary_csv(result, output_summary) if output_summary else None
    problem_path = write_noord_brabant_realworks_problem_sources_csv(result, output_problem_sources) if output_problem_sources else None
    return NoordBrabantRealworksAuditResult(
        sources=result.sources,
        metrics=result.metrics,
        readiness_results=result.readiness_results,
        aggregate_metrics=result.aggregate_metrics,
        family_decision=result.family_decision,
        observed_at=result.observed_at,
        workbook_path=workbook_path,
        summary_csv_path=summary_path,
        problem_sources_csv_path=problem_path,
        warnings=result.warnings,
    )


def aggregate_noord_brabant_realworks_metrics(
    *,
    input_sources: int,
    attempted_sources: int,
    metrics: Sequence[NoordBrabantRealworksAuditMetrics],
    runtime_budget_exhausted: bool,
) -> NoordBrabantRealworksAggregateMetrics:
    statuses = Counter(metric.validation_status for metric in metrics)
    return NoordBrabantRealworksAggregateMetrics(
        input_sources=input_sources,
        sources_attempted=attempted_sources,
        sources_skipped=max(0, input_sources - attempted_sources),
        sources_passed=statuses["passed"],
        sources_passed_with_review_gaps=statuses["passed_with_review_gaps"],
        sources_no_current_listings=statuses["no_current_listings"],
        sources_blocked=statuses["blocked_by_robots"] + statuses["blocked_by_http_status"],
        sources_fetch_failed=statuses["listing_fetch_failed"],
        sources_needing_hardening=statuses["needs_realworks_hardening"],
        total_parser_rows=sum(metric.parser_total for metric in metrics),
        total_qa_clean=sum(metric.parser_qa_clean for metric in metrics),
        total_qa_review=sum(metric.parser_qa_review for metric in metrics),
        total_qa_rejected=sum(metric.parser_qa_rejected for metric in metrics),
        total_detail_attempted=sum(metric.detail_attempted for metric in metrics),
        total_detail_succeeded=sum(metric.detail_succeeded for metric in metrics),
        total_detail_failed=sum(metric.detail_failed for metric in metrics),
        total_readiness_rows=sum(metric.readiness_rows_built for metric in metrics),
        total_export_ready=sum(metric.export_ready for metric in metrics),
        total_export_review=sum(metric.export_review for metric in metrics),
        total_export_blocked=sum(metric.export_blocked for metric in metrics),
        field_gap_counts=_sum_counter_pairs(metric.field_gap_counts for metric in metrics),
        warning_counts=_sum_counter_pairs(metric.warning_counts for metric in metrics),
        failure_pattern_counts=_sum_counter_pairs((tuple((pattern, 1) for pattern in metric.failure_patterns) for metric in metrics)),
        runtime_budget_exhausted=runtime_budget_exhausted,
    )


def decide_noord_brabant_realworks_family(
    metrics: Sequence[NoordBrabantRealworksAuditMetrics],
    aggregate: NoordBrabantRealworksAggregateMetrics,
) -> NoordBrabantRealworksFamilyDecision:
    attempted = max(1, aggregate.sources_attempted)
    successful = aggregate.sources_passed + aggregate.sources_passed_with_review_gaps
    blocked = aggregate.sources_blocked
    hardening = aggregate.sources_needing_hardening
    fetch_failed = aggregate.sources_fetch_failed
    no_current = aggregate.sources_no_current_listings
    source_exclusions = tuple(
        metric.source_id
        for metric in metrics
        if metric.validation_status in {"blocked_by_robots", "blocked_by_http_status", "listing_fetch_failed", "no_current_listings"}
    )
    hardening_targets = tuple(
        warning for warning, count in aggregate.failure_pattern_counts if count >= 2 or warning in {"parser_zero_qa_clean", "detail_systemic_failure"}
    )

    if blocked / attempted >= 0.60:
        return NoordBrabantRealworksFamilyDecision(
            family_decision="blocked_by_access_policy",
            confidence="medium",
            reasons=("broad_access_or_robots_blocking",),
            next_action="Stop operational use until access policy permits a meaningful Realworks audit.",
            source_exclusions=source_exclusions,
            hardening_targets=hardening_targets,
        )
    if hardening >= 3 or (hardening and hardening >= successful):
        return NoordBrabantRealworksFamilyDecision(
            family_decision="realworks_needs_hardening_v2",
            confidence="medium",
            reasons=("systemic_parser_or_detail_failure_patterns",),
            next_action="Run Realworks Hardening v2 before merge or broader family coverage.",
            source_exclusions=source_exclusions,
            hardening_targets=hardening_targets,
        )
    if aggregate.sources_attempted == 0 or successful < 2:
        return NoordBrabantRealworksFamilyDecision(
            family_decision="insufficient_successful_sources",
            confidence="low",
            reasons=("too_few_successful_sources",),
            next_action="Do not proceed to family coverage; rerun when enough sources can be audited.",
            source_exclusions=source_exclusions,
            hardening_targets=hardening_targets,
        )
    if successful / attempted >= 0.60 and aggregate.total_readiness_rows > 0 and not hardening:
        if blocked or fetch_failed or no_current or aggregate.runtime_budget_exhausted:
            return NoordBrabantRealworksFamilyDecision(
                family_decision="realworks_partially_ready_with_exclusions",
                confidence="medium",
                reasons=("parser_works_broadly_with_isolated_exclusions",),
                next_action="Review exclusions and rerun blocked or empty sources before operational promotion.",
                source_exclusions=source_exclusions,
                hardening_targets=hardening_targets,
            )
        return NoordBrabantRealworksFamilyDecision(
            family_decision="realworks_ready_for_nb_family_coverage",
            confidence="high",
            reasons=("majority_sources_passed", "readiness_rows_built_across_sources"),
            next_action="Merge if manual workbook review confirms the rows; do not start matching in this phase.",
            source_exclusions=(),
            hardening_targets=(),
        )
    return NoordBrabantRealworksFamilyDecision(
        family_decision="realworks_partially_ready_with_exclusions",
        confidence="low",
        reasons=("mixed_results_need_review",),
        next_action="Review exclusions and failure patterns before deciding on Realworks Hardening v2.",
        source_exclusions=source_exclusions,
        hardening_targets=hardening_targets,
    )


def write_noord_brabant_realworks_audit_workbook(
    result: NoordBrabantRealworksAuditResult,
    output_path: Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    workbook.active.title = "Source Summary"
    _write_source_summary(workbook["Source Summary"], result.metrics)
    _write_realworks_properties(workbook.create_sheet("Realworks Properties"), result.readiness_results)
    _write_field_gaps(workbook.create_sheet("Field Gaps"), result.aggregate_metrics.field_gap_counts)
    _write_warnings(workbook.create_sheet("Warnings"), result.aggregate_metrics.warning_counts)
    _write_problem_sources(workbook.create_sheet("Problem Sources"), result.metrics)
    _write_parser_failure_patterns(workbook.create_sheet("Parser Failure Patterns"), result.aggregate_metrics.failure_pattern_counts)
    _write_access_policy(workbook.create_sheet("Access Policy"), result.metrics)
    _write_audit_input(workbook.create_sheet("Audit Input"), result.sources)
    _write_family_decision(workbook.create_sheet("Family Audit Decision"), result.family_decision)
    _write_manual_verification(workbook.create_sheet("Manual Verification"), result.sources, result.readiness_results)
    for worksheet in workbook.worksheets:
        _format_sheet(worksheet)
    workbook.save(output_path)
    return output_path


def write_noord_brabant_realworks_summary_csv(
    result: NoordBrabantRealworksAuditResult,
    output_path: Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        for metric in result.metrics:
            writer.writerow({column: _safe_cell(_metric_value(metric, column)) for column in SUMMARY_COLUMNS})
    return output_path


def write_noord_brabant_realworks_problem_sources_csv(
    result: NoordBrabantRealworksAuditResult,
    output_path: Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    columns = (
        "source_id",
        "domain",
        "accepted_aanbod_url",
        "validation_status",
        "validation_decision",
        "recommended_next_action",
        "top_warning",
        "failure_patterns",
    )
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for metric in result.metrics:
            if metric.validation_status in {"passed", "passed_with_review_gaps"}:
                continue
            writer.writerow(
                {
                    "source_id": _safe_cell(metric.source_id),
                    "domain": _safe_cell(metric.domain),
                    "accepted_aanbod_url": _safe_cell(metric.accepted_aanbod_url),
                    "validation_status": metric.validation_status,
                    "validation_decision": metric.validation_decision,
                    "recommended_next_action": metric.recommended_next_action,
                    "top_warning": metric.top_warning,
                    "failure_patterns": _join(metric.failure_patterns),
                }
            )
    return output_path


def _metrics_for_source(
    source: NoordBrabantRealworksAuditSource,
    readiness: RealworksPropertyReadinessResult,
) -> NoordBrabantRealworksAuditMetrics:
    rows = tuple(readiness.rows)
    export_counts = Counter(row.export_readiness for row in rows)
    validation_status = _validation_status(readiness)
    warning_counts = tuple(sorted(Counter(warning for warning in readiness.warnings if warning).items()))
    field_gaps = _field_gap_counts(readiness, rows)
    failure_patterns = _failure_patterns(readiness, validation_status)
    return NoordBrabantRealworksAuditMetrics(
        source_id=source.source_id,
        source_name=source.source_name,
        domain=source.domain,
        accepted_aanbod_url=source.accepted_aanbod_url,
        coverage_city=source.coverage_city,
        coverage_gemeente=source.coverage_gemeente,
        aanbod_scope_status=source.aanbod_scope_status,
        access_policy_status="allowed",
        robots_listing_allowed="listing_blocked_by_robots" not in readiness.warnings,
        listing_fetch_status=_listing_fetch_status(readiness),
        listing_http_status=_listing_http_status(readiness),
        parser_total=readiness.listing_parser_total,
        parser_qa_clean=readiness.listing_qa_clean,
        parser_qa_review=readiness.listing_qa_review,
        parser_qa_rejected=readiness.listing_qa_rejected,
        detail_attempted=readiness.detail_attempted,
        detail_succeeded=readiness.detail_succeeded,
        detail_failed=readiness.detail_failed,
        readiness_rows_built=readiness.readiness_rows_built,
        export_ready=export_counts["export_ready"],
        export_review=export_counts["export_review"],
        export_blocked=export_counts["export_blocked"],
        active_inventory_eligible=sum(1 for row in rows if row.active_inventory_eligible),
        inactive_status_count=sum(1 for row in rows if row.status_bucket.startswith("inactive_")),
        non_residential_count=sum(1 for row in rows if row.residential_classification.startswith("non_residential")),
        no_current_listings=validation_status == "no_current_listings",
        top_warning=warning_counts[0][0] if warning_counts else "",
        warning_counts=warning_counts,
        field_gap_counts=field_gaps,
        failure_patterns=failure_patterns,
        validation_status=validation_status,
        validation_decision=_validation_decision(validation_status),
        recommended_next_action=_recommended_next_action(validation_status),
    )


def _validation_status(readiness: RealworksPropertyReadinessResult) -> str:
    warnings = set(readiness.warnings)
    if "listing_blocked_by_robots" in warnings:
        return "blocked_by_robots"
    if "listing_fetch_parse_or_qa_exception" in warnings or "source_runner_exception" in warnings:
        return "listing_fetch_failed"
    if readiness.listing_parser_total <= 0:
        return "no_current_listings"
    if readiness.listing_qa_clean <= 0:
        return "needs_realworks_hardening"
    if readiness.detail_attempted > 0 and readiness.detail_succeeded == 0:
        return "needs_realworks_hardening"
    if readiness.readiness_rows_built <= 0:
        return "needs_realworks_hardening"
    if readiness.detail_failed > readiness.detail_succeeded:
        return "detail_fetch_failures"
    if _has_review_gaps(readiness.rows):
        return "passed_with_review_gaps"
    return "passed"


def _validation_decision(status: str) -> str:
    return {
        "passed": "source passed without source-specific code",
        "passed_with_review_gaps": "source passed with explicit review gaps",
        "no_current_listings": "listing page fetched but no current listing rows were built",
        "blocked_by_robots": "source blocked by robots or access gate",
        "blocked_by_http_status": "source blocked by HTTP status",
        "listing_fetch_failed": "listing fetch, parser, or QA failed",
        "detail_fetch_failures": "detail pages failed more often than they succeeded",
        "needs_realworks_hardening": "reusable Realworks family needs hardening for this source",
    }.get(status, "manual review needed")


def _recommended_next_action(status: str) -> str:
    return {
        "passed": "keep in Realworks family coverage candidate set",
        "passed_with_review_gaps": "manual workbook review before operational promotion",
        "no_current_listings": "exclude from parser hardening unless listings reappear",
        "blocked_by_robots": "do not fetch until access policy changes",
        "blocked_by_http_status": "exclude or review source access policy",
        "listing_fetch_failed": "review fetch/access failure before rerun",
        "detail_fetch_failures": "review detail access and extraction failures",
        "needs_realworks_hardening": "include in Realworks Hardening v2",
    }.get(status, "manual review")


def _listing_fetch_status(readiness: RealworksPropertyReadinessResult) -> str:
    warnings = set(readiness.warnings)
    if "listing_blocked_by_robots" in warnings:
        return "robots_blocked"
    if "listing_fetch_parse_or_qa_exception" in warnings or "source_runner_exception" in warnings:
        return "failed"
    if readiness.listing_parser_total <= 0:
        return "success_empty"
    return "success"


def _listing_http_status(readiness: RealworksPropertyReadinessResult) -> str:
    if "listing_blocked_by_robots" in readiness.warnings:
        return "not_fetched_robots"
    if "listing_fetch_parse_or_qa_exception" in readiness.warnings:
        return "fetch_or_parse_exception"
    return "ok_or_not_reported"


def _failure_patterns(readiness: RealworksPropertyReadinessResult, validation_status: str) -> tuple[str, ...]:
    patterns: list[str] = []
    if readiness.listing_parser_total <= 0 and validation_status == "no_current_listings":
        patterns.append("no_current_listings")
    if readiness.listing_parser_total > 0 and readiness.listing_qa_clean <= 0:
        patterns.append("parser_zero_qa_clean")
    if readiness.detail_attempted > 0 and readiness.detail_succeeded == 0:
        patterns.append("detail_systemic_failure")
    if validation_status in {"blocked_by_robots", "listing_fetch_failed", "detail_fetch_failures", "needs_realworks_hardening"}:
        patterns.append(validation_status)
    patterns.extend(warning for warning in readiness.warnings if warning in {"no_realworks_detail_urls_found", "empty_parser_input"})
    return _dedupe(patterns)


def _input_gate_counts(rows: Sequence[Mapping[str, str]]) -> dict[str, int]:
    return {
        "audit_input_missing_file_count": 0,
        "audit_input_non_ready_count": sum(1 for row in rows if row.get("audit_input_status") != REALWORKS_READY_STATUS),
        "audit_input_non_realworks_count": sum(1 for row in rows if row.get("parser_family_candidate") != REALWORKS_FAMILY),
        "audit_input_kin_count": sum(1 for row in rows if "kin" in _normalize_key(f"{row.get('domain', '')} {row.get('source_id', '')}")),
        "audit_input_missing_accepted_aanbod_url_count": sum(1 for row in rows if not _clean_text(row.get("accepted_aanbod_url"))),
        "audit_input_property_detail_url_count": sum(1 for row in rows if _looks_like_property_detail_url(_clean_text(row.get("accepted_aanbod_url")))),
        "audit_input_funda_pararius_count": sum(1 for row in rows if _is_funda_or_pararius(_clean_text(row.get("accepted_aanbod_url")))),
    }


def _source_from_row(row: Mapping[str, str]) -> NoordBrabantRealworksAuditSource:
    return NoordBrabantRealworksAuditSource(
        source_id=_clean_text(row.get("source_id")),
        source_name=_clean_text(row.get("source_name")) or _clean_text(row.get("source_id")),
        domain=_normalize_domain(row.get("domain")),
        accepted_aanbod_url=_clean_text(row.get("accepted_aanbod_url")),
        coverage_city=_clean_text(row.get("coverage_city")),
        coverage_gemeente=_clean_text(row.get("coverage_gemeente")),
        coverage_province=_clean_text(row.get("coverage_province")),
        aanbod_scope_status=_clean_text(row.get("aanbod_scope_status")),
        realworks_verification_status=_clean_text(row.get("realworks_verification_status")),
        realworks_evidence_strength=_clean_text(row.get("realworks_evidence_strength")),
        audit_input_status=_clean_text(row.get("audit_input_status")),
        parser_family_candidate=_clean_text(row.get("parser_family_candidate")),
    )


def _validate_source(source: NoordBrabantRealworksAuditSource) -> str:
    if not source.source_id or not source.domain or not source.accepted_aanbod_url:
        return "missing source_id/domain/accepted_aanbod_url"
    if source.audit_input_status != REALWORKS_READY_STATUS:
        return "non-ready audit input row"
    if source.parser_family_candidate != REALWORKS_FAMILY:
        return "non-Realworks parser family"
    if source.realworks_verification_status != REALWORKS_VERIFIED:
        return "unverified Realworks source"
    if "kin" in _normalize_key(f"{source.domain} {source.source_id}"):
        return "KIN row is not allowed"
    if _is_funda_or_pararius(source.accepted_aanbod_url):
        return "Funda/Pararius URL is not allowed"
    if _looks_like_property_detail_url(source.accepted_aanbod_url):
        return "accepted_aanbod_url is a property detail URL"
    if not _url_matches_domain(source.accepted_aanbod_url, source.domain):
        return "accepted_aanbod_url is not on official domain"
    return ""


def _has_review_gaps(rows: Sequence[RealworksPropertyReadinessRow]) -> bool:
    return any(
        row.quality_status != "client_ready"
        or row.missing_key_fields
        or row.review_fields
        or row.export_readiness != "export_ready"
        for row in rows
    )


def _field_gap_counts(
    readiness: RealworksPropertyReadinessResult,
    rows: Sequence[RealworksPropertyReadinessRow],
) -> tuple[tuple[str, int], ...]:
    counts: Counter[str] = Counter()
    for field, _usable, review, missing in readiness.field_completion_counts:
        if review:
            counts[f"review:{field}"] += review
        if missing:
            counts[field] += missing
    for row in rows:
        counts.update(row.missing_key_fields)
        counts.update(f"review:{field}" for field in row.review_fields)
    return tuple(counts.most_common())


def _empty_readiness_result(
    source: NoordBrabantRealworksAuditSource,
    warnings: Iterable[str],
) -> RealworksPropertyReadinessResult:
    return RealworksPropertyReadinessResult(
        source_id=source.source_id,
        source_domain=source.domain,
        listing_parser_total=0,
        listing_qa_clean=0,
        listing_qa_review=0,
        listing_qa_rejected=0,
        detail_attempted=0,
        detail_succeeded=0,
        detail_failed=0,
        facts_records_built=0,
        readiness_rows_built=0,
        quality_status_counts=(),
        export_readiness_counts=(),
        field_completion_counts=(),
        missing_key_fields_counts=(),
        review_fields_counts=(),
        warning_counts=(),
        sample_rows_compact=(),
        problem_rows_compact=(),
        excel_validation_ready=False,
        rows=(),
        warnings=tuple(warnings),
    )


def _write_source_summary(worksheet: Worksheet, metrics: Sequence[NoordBrabantRealworksAuditMetrics]) -> None:
    worksheet.append(SUMMARY_COLUMNS)
    for metric in metrics:
        worksheet.append([_safe_cell(_metric_value(metric, column)) for column in SUMMARY_COLUMNS])


def _write_realworks_properties(
    worksheet: Worksheet,
    readiness_results: Sequence[RealworksPropertyReadinessResult],
) -> None:
    columns = (
        "source_id",
        "source_domain",
        "canonical_url",
        "address",
        "postcode",
        "city",
        "asking_price",
        "status_bucket",
        "quality_status",
        "export_readiness",
        "active_inventory_eligible",
        "residential_classification",
        "freshness_bucket",
        "lifecycle_events",
        "missing_key_fields",
        "review_fields",
        "warnings",
    )
    worksheet.append(columns)
    for readiness in readiness_results:
        for row in readiness.rows:
            values = {
                "source_id": row.source_id,
                "source_domain": row.source_domain,
                "canonical_url": row.canonical_url,
                "address": row.address,
                "postcode": row.postcode,
                "city": row.city,
                "asking_price": row.asking_price,
                "status_bucket": row.status_bucket,
                "quality_status": row.quality_status,
                "export_readiness": row.export_readiness,
                "active_inventory_eligible": row.active_inventory_eligible,
                "residential_classification": row.residential_classification,
                "freshness_bucket": row.freshness_bucket,
                "lifecycle_events": _join(row.lifecycle_events),
                "missing_key_fields": _join(row.missing_key_fields),
                "review_fields": _join(row.review_fields),
                "warnings": _join(row.warnings),
            }
            worksheet.append([_safe_cell(values[column]) for column in columns])


def _write_field_gaps(worksheet: Worksheet, counts: Sequence[tuple[str, int]]) -> None:
    worksheet.append(("field", "count"))
    for field, count in counts:
        worksheet.append((_safe_cell(field), count))


def _write_warnings(worksheet: Worksheet, counts: Sequence[tuple[str, int]]) -> None:
    worksheet.append(("warning", "count"))
    for warning, count in counts:
        worksheet.append((_safe_cell(warning), count))


def _write_problem_sources(worksheet: Worksheet, metrics: Sequence[NoordBrabantRealworksAuditMetrics]) -> None:
    columns = ("source_id", "domain", "accepted_aanbod_url", "validation_status", "validation_decision", "recommended_next_action", "top_warning", "failure_patterns")
    worksheet.append(columns)
    for metric in metrics:
        if metric.validation_status in {"passed", "passed_with_review_gaps"}:
            continue
        worksheet.append(
            (
                _safe_cell(metric.source_id),
                _safe_cell(metric.domain),
                _safe_cell(metric.accepted_aanbod_url),
                metric.validation_status,
                metric.validation_decision,
                metric.recommended_next_action,
                _safe_cell(metric.top_warning),
                _join(metric.failure_patterns),
            )
        )


def _write_parser_failure_patterns(worksheet: Worksheet, counts: Sequence[tuple[str, int]]) -> None:
    worksheet.append(("failure_pattern", "count"))
    for pattern, count in counts:
        worksheet.append((_safe_cell(pattern), count))


def _write_access_policy(worksheet: Worksheet, metrics: Sequence[NoordBrabantRealworksAuditMetrics]) -> None:
    columns = ("source_id", "domain", "accepted_aanbod_url", "access_policy_status", "robots_listing_allowed", "listing_fetch_status")
    worksheet.append(columns)
    for metric in metrics:
        worksheet.append([_safe_cell(_metric_value(metric, column)) for column in columns])


def _write_audit_input(worksheet: Worksheet, sources: Sequence[NoordBrabantRealworksAuditSource]) -> None:
    columns = tuple(NoordBrabantRealworksAuditSource.__dataclass_fields__)
    worksheet.append(columns)
    for source in sources:
        worksheet.append([_safe_cell(getattr(source, column)) for column in columns])


def _write_family_decision(worksheet: Worksheet, decision: NoordBrabantRealworksFamilyDecision) -> None:
    worksheet.append(("field", "value"))
    for field in NoordBrabantRealworksFamilyDecision.__dataclass_fields__:
        value = getattr(decision, field)
        worksheet.append((field, _join(value) if isinstance(value, tuple) else _safe_cell(value)))


def _write_manual_verification(
    worksheet: Worksheet,
    sources: Sequence[NoordBrabantRealworksAuditSource],
    readiness_results: Sequence[RealworksPropertyReadinessResult],
) -> None:
    source_by_id = {source.source_id: source for source in sources}
    worksheet.append(MANUAL_VERIFICATION_COLUMNS)
    for readiness in readiness_results:
        source = source_by_id.get(readiness.source_id)
        for row in readiness.rows:
            values = {
                "source_id": row.source_id,
                "domain": row.source_domain,
                "address": row.address,
                "city": row.city,
                "price": row.asking_price,
                "status": row.status_bucket,
                "accepted_aanbod_url": source.accepted_aanbod_url if source else "",
                "canonical_url": row.canonical_url,
                "property_link": "Open listing" if _is_http_url(row.canonical_url) else "",
                "export_readiness": row.export_readiness,
                "quality_status": row.quality_status,
                "missing_key_fields": _join(row.missing_key_fields),
                "warnings": _join(row.warnings),
                "manual_check_result": "",
                "manual_check_notes": "",
            }
            worksheet.append([_safe_cell(values[column]) for column in MANUAL_VERIFICATION_COLUMNS])
            link_cell = worksheet.cell(worksheet.max_row, MANUAL_VERIFICATION_COLUMNS.index("property_link") + 1)
            if _is_http_url(row.canonical_url):
                link_cell.hyperlink = row.canonical_url
                link_cell.style = "Hyperlink"


def _format_sheet(worksheet: Worksheet) -> None:
    if worksheet.max_row < 1 or worksheet.max_column < 1:
        return
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions
    fill = PatternFill("solid", fgColor="D9EAF7")
    for cell in worksheet[1]:
        cell.font = Font(bold=True)
        cell.fill = fill
    for column_cells in worksheet.columns:
        letter = get_column_letter(column_cells[0].column)
        max_length = max(len(str(cell.value or "")) for cell in column_cells[:100])
        worksheet.column_dimensions[letter].width = max(10, min(max_length + 2, 60))


def _sum_counter_pairs(counter_pairs: Iterable[Iterable[tuple[str, int]]]) -> tuple[tuple[str, int], ...]:
    counts: Counter[str] = Counter()
    for pairs in counter_pairs:
        for key, count in pairs:
            if key:
                counts[key] += count
    return tuple(counts.most_common())


def _runtime_exhausted(start: float, budget_seconds: float) -> bool:
    return budget_seconds >= 0 and (time.monotonic() - start) >= budget_seconds


def _metric_value(metric: NoordBrabantRealworksAuditMetrics, column: str) -> object:
    value = getattr(metric, column)
    if isinstance(value, tuple):
        return _join(f"{key}={count}" for key, count in value)
    return value


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return " ".join(_clean_text(item) for item in value if _clean_text(item))
    return str(value).strip()


def _normalize_key(value: object) -> str:
    return _clean_text(value).casefold().replace("-", "_").replace(" ", "_")


def _normalize_domain(value: object) -> str:
    text = _clean_text(value).lower()
    if not text:
        return ""
    parts = urlsplit(text if "://" in text else f"https://{text}")
    host = (parts.netloc or parts.path).split("/", 1)[0].split(":", 1)[0].strip().lower()
    return host[4:] if host.startswith("www.") else host


def _normalize_url(value: object) -> str:
    parts = urlsplit(_clean_text(value))
    if not parts.scheme or not parts.netloc:
        return _clean_text(value).casefold().rstrip("/")
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}{(parts.path or '/').rstrip('/')}".casefold()


def _url_matches_domain(url: str, domain: str) -> bool:
    host = _normalize_domain(urlsplit(url).netloc)
    normalized_domain = _normalize_domain(domain)
    return bool(host and normalized_domain and (host == normalized_domain or host.endswith(f".{normalized_domain}")))


def _is_funda_or_pararius(value: str) -> bool:
    text = _clean_text(value).casefold()
    return "funda.nl" in text or "pararius.nl" in text


def _looks_like_property_detail_url(value: str) -> bool:
    path = urlsplit(_clean_text(value)).path.casefold().rstrip("/")
    return any(
        marker in path
        for marker in (
            "/huis-",
            "/appartement-",
            "/woning-",
            "/aanbod/woningaanbod/koop/",
            "/aanbod/woningaanbod/huur/",
        )
    )


def _is_http_url(value: object) -> bool:
    parts = urlsplit(_clean_text(value))
    return parts.scheme in {"http", "https"} and bool(parts.netloc)


def _safe_cell(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, (int, float, bool)):
        return value
    text = " ".join(str(value).split())
    lowered = text.casefold()
    if any(marker in lowered for marker in RAW_MARKERS):
        return ""
    if len(text) > LONG_TEXT_LIMIT:
        return "[long_text_omitted]"
    return text


def _join(values: Iterable[object]) -> str:
    return "; ".join(str(_safe_cell(value)) for value in values if _safe_cell(value) not in (None, ""))


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
