from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from domek_wonen.facts.cache import PropertyFactsCache
from domek_wonen.pilots.kin_full_property_readiness import (
    KINFullPropertyReadinessResult,
    KINPropertyReadinessRow,
    MAX_KIN_READINESS_DETAILS,
    run_kin_full_property_readiness,
)


_FIELD_GAP_FIELDS = (
    "asking_price",
    "property_type",
    "living_area_m2",
    "plot_area_m2",
    "rooms",
    "bedrooms",
    "bathrooms",
    "energy_label",
    "eigendomssituatie",
    "vve_monthly_cost",
    "vve_active",
    "heating_type",
    "cv_ketel_ownership",
    "garden",
    "balcony",
    "storage",
    "garage",
    "parking",
    "availability_date",
    "open_huis_badge_or_event",
)
_LOCATION_GAP_FIELDS = ("postcode", "city", "address_raw", "latitude", "longitude")
_PROBLEM_ROW_LIMIT = 10


@dataclass(frozen=True, slots=True)
class KINFieldGap:
    field: str
    missing_count: int
    review_count: int
    usable_count: int
    total_rows: int
    missing_rate: float
    review_rate: float


@dataclass(frozen=True, slots=True)
class KINProblemRow:
    canonical_url: str
    address_raw: str | None
    postcode: str | None
    city: str | None
    listing_status: str | None
    location_status: str
    export_readiness: str
    quality_status: str
    missing_key_fields: tuple[str, ...]
    attention_points: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class KINCoverageCompletionResult:
    source_id: str
    source_domain: str

    total_listings_seen: int
    qa_clean_count: int
    target_rows: int
    rows_built: int
    coverage_rate: float

    completed: bool
    partial: bool

    cache_hits: int
    cache_misses: int
    detail_fetch_attempted: int
    detail_fetch_succeeded: int
    detail_fetch_failed: int
    records_written: int

    location_usable_count: int
    location_review_count: int
    location_missing_count: int

    export_ready_count: int
    export_review_count: int
    export_blocked_count: int

    client_ready_count: int
    advisor_review_count: int
    insufficient_location_count: int
    insufficient_facts_count: int

    field_completion_counts: tuple[tuple[str, int], ...]
    missing_key_field_counts: tuple[tuple[str, int], ...]
    attention_point_counts: tuple[tuple[str, int], ...]
    warning_counts: tuple[tuple[str, int], ...]

    field_gaps: tuple[KINFieldGap, ...]
    top_blockers: tuple[tuple[str, int], ...]
    sample_problem_rows: tuple[object, ...]
    warnings: tuple[str, ...] = ()


def run_kin_full_coverage_completion_audit(
    *,
    config_path: Path,
    cache_path: Path,
    max_api_pages: int = 25,
    max_details: int = 300,
    max_runtime_seconds: float | None = None,
    force_refresh: bool = False,
) -> KINCoverageCompletionResult:
    if cache_path is None:
        raise ValueError("cache_path_required")

    effective_max_details = _effective_resume_detail_limit(
        cache_path=Path(cache_path),
        max_details=max_details,
        force_refresh=force_refresh,
    )
    readiness = run_kin_full_property_readiness(
        config_path=config_path,
        cache_path=cache_path,
        max_api_pages=max_api_pages,
        max_details=effective_max_details,
        max_runtime_seconds=max_runtime_seconds,
        force_refresh=force_refresh,
    )
    return build_kin_full_coverage_completion_result(readiness)


def build_kin_full_coverage_completion_result(
    readiness: KINFullPropertyReadinessResult,
) -> KINCoverageCompletionResult:
    rows = _result_rows(readiness)
    target_rows = readiness.qa_clean_count
    rows_built = readiness.rows_built
    completed = rows_built >= target_rows if target_rows else rows_built == 0
    warnings = list(readiness.warnings)
    if not completed:
        warnings.append("kin_coverage_incomplete")
    if "kin_readiness_runtime_budget_exhausted" in readiness.warnings:
        warnings.append("kin_coverage_runtime_budget_exhausted")
    if "detail_fetch_exception" in readiness.warnings:
        warnings.append("detail_fetch_exception")

    quality_counts = Counter(row.quality_status for row in rows)
    return KINCoverageCompletionResult(
        source_id=readiness.source_id,
        source_domain=readiness.source_domain,
        total_listings_seen=readiness.listings_seen,
        qa_clean_count=readiness.qa_clean_count,
        target_rows=target_rows,
        rows_built=rows_built,
        coverage_rate=_rate(rows_built, target_rows),
        completed=completed,
        partial=not completed,
        cache_hits=readiness.cache_hits,
        cache_misses=readiness.cache_misses,
        detail_fetch_attempted=readiness.detail_fetch_attempted,
        detail_fetch_succeeded=readiness.detail_fetch_succeeded,
        detail_fetch_failed=readiness.detail_fetch_failed,
        records_written=readiness.records_written,
        location_usable_count=readiness.location_usable_count,
        location_review_count=readiness.location_review_count,
        location_missing_count=readiness.location_missing_count,
        export_ready_count=readiness.export_ready_count,
        export_review_count=readiness.export_review_count,
        export_blocked_count=readiness.export_blocked_count,
        client_ready_count=quality_counts["client_ready"],
        advisor_review_count=quality_counts["advisor_review"],
        insufficient_location_count=quality_counts["insufficient_location"],
        insufficient_facts_count=quality_counts["insufficient_facts"],
        field_completion_counts=readiness.field_completion_counts,
        missing_key_field_counts=readiness.missing_key_field_counts,
        attention_point_counts=readiness.attention_point_counts,
        warning_counts=readiness.warning_counts,
        field_gaps=_field_gaps(rows),
        top_blockers=_top_blockers(readiness, rows),
        sample_problem_rows=_sample_problem_rows(rows),
        warnings=_dedupe(warnings),
    )


def _effective_resume_detail_limit(*, cache_path: Path, max_details: int, force_refresh: bool) -> int:
    if max_details <= 0:
        return 0
    if force_refresh:
        return min(max_details, MAX_KIN_READINESS_DETAILS)
    cached_count = len(PropertyFactsCache(cache_path).load_all())
    return min(MAX_KIN_READINESS_DETAILS, max(max_details, max_details + cached_count))


def _result_rows(readiness: KINFullPropertyReadinessResult) -> tuple[KINPropertyReadinessRow, ...]:
    rows = getattr(readiness, "rows", ())
    if rows:
        return tuple(rows)
    return tuple(readiness.sample_rows)


def _field_gaps(rows: tuple[KINPropertyReadinessRow, ...]) -> tuple[KINFieldGap, ...]:
    return tuple(_fact_field_gap(field, rows) for field in _FIELD_GAP_FIELDS) + tuple(
        _location_field_gap(field, rows) for field in _LOCATION_GAP_FIELDS
    )


def _fact_field_gap(field: str, rows: tuple[KINPropertyReadinessRow, ...]) -> KINFieldGap:
    usable = 0
    review = 0
    missing = 0
    for row in rows:
        facts = {fact.field: fact.status for fact in row.facts_record.facts}
        if facts.get(field) == "usable":
            usable += 1
        elif facts.get(field) == "review":
            review += 1
        else:
            missing += 1
    return _gap(field, usable=usable, review=review, missing=missing, total=len(rows))


def _location_field_gap(field: str, rows: tuple[KINPropertyReadinessRow, ...]) -> KINFieldGap:
    usable = 0
    missing = 0
    for row in rows:
        value = getattr(row, field)
        if value is None or value == "":
            missing += 1
        else:
            usable += 1
    return _gap(field, usable=usable, review=0, missing=missing, total=len(rows))


def _gap(field: str, *, usable: int, review: int, missing: int, total: int) -> KINFieldGap:
    return KINFieldGap(
        field=field,
        missing_count=missing,
        review_count=review,
        usable_count=usable,
        total_rows=total,
        missing_rate=_rate(missing, total),
        review_rate=_rate(review, total),
    )


def _top_blockers(
    readiness: KINFullPropertyReadinessResult,
    rows: tuple[KINPropertyReadinessRow, ...],
) -> tuple[tuple[str, int], ...]:
    counts: Counter[str] = Counter()
    counts.update({f"missing_key_field:{field}": count for field, count in readiness.missing_key_field_counts})
    counts.update({f"attention_point:{point}": count for point, count in readiness.attention_point_counts})
    counts.update({f"warning:{warning}": count for warning, count in readiness.warning_counts})
    counts.update(row.quality_status for row in rows)
    counts.update(row.export_readiness for row in rows if row.export_readiness == "export_blocked")
    counts.update("missing_coordinates" for row in rows if row.latitude is None or row.longitude is None)
    return tuple(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _sample_problem_rows(rows: tuple[KINPropertyReadinessRow, ...]) -> tuple[object, ...]:
    ranked = sorted(rows, key=_problem_rank, reverse=True)
    return tuple(_problem_snapshot(row) for row in ranked if _problem_rank(row) > 0)[:_PROBLEM_ROW_LIMIT]


def _problem_rank(row: KINPropertyReadinessRow) -> int:
    score = 0
    if row.export_readiness == "export_blocked":
        score += 5
    if row.quality_status in {"insufficient_location", "insufficient_facts"}:
        score += 4
    score += min(4, len(row.missing_key_fields))
    if any("property_type" in point for point in row.attention_points):
        score += 2
    if "detail_fetch_exception" in row.warnings:
        score += 2
    return score


def _problem_snapshot(row: KINPropertyReadinessRow) -> KINProblemRow:
    return KINProblemRow(
        canonical_url=row.canonical_url,
        address_raw=row.address_raw,
        postcode=row.postcode,
        city=row.city,
        listing_status=row.listing_status,
        location_status=row.location_status,
        export_readiness=row.export_readiness,
        quality_status=row.quality_status,
        missing_key_fields=row.missing_key_fields,
        attention_points=row.attention_points,
        warnings=row.warnings,
    )


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)
