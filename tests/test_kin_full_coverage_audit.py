from __future__ import annotations

import ast
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
import sys


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.facts import PropertyFactsCache, build_property_fact_value, build_property_facts_record  # noqa: E402
from domek_wonen.parsers.models import ParsedListing  # noqa: E402
from domek_wonen.pilots import kin_full_coverage_audit as audit_module  # noqa: E402
from domek_wonen.pilots.kin_full_coverage_audit import (  # noqa: E402
    build_kin_full_coverage_completion_result,
    run_kin_full_coverage_completion_audit,
)
from domek_wonen.pilots.kin_full_property_readiness import (  # noqa: E402
    KINFullPropertyReadinessResult,
    build_kin_property_readiness_row,
)


CONFIG_FIXTURE = BASE_DIR / "tests" / "fixtures" / "parsers" / "kin_ogonline_xhr_source_config.json"
MODULE_PATH = BASE_DIR / "scraper" / "src" / "domek_wonen" / "pilots" / "kin_full_coverage_audit.py"
NOW = datetime(2026, 6, 27, tzinfo=UTC)


def _listing(index: int, **overrides: object) -> ParsedListing:
    listing = ParsedListing(
        source_id="kinmakelaars.nl__breda",
        source_domain="kinmakelaars.nl",
        canonical_url=f"https://kinmakelaars.nl/aanbod/wonen/breda/audit-{index}/kin-audit-{index:03d}",
        address_raw=f"Auditstraat {index}",
        street="Auditstraat",
        house_number=str(index),
        postcode="4811AA",
        city="Breda",
        asking_price_eur=425000 + index,
        transaction_type="koop",
        status="beschikbaar",
        living_area_m2=120 + index,
        rooms_count=5,
        bedrooms_count=3,
        property_type="Tussenwoning",
        energy_label="A",
        confidence_score=0.95,
    )
    values = {field: getattr(listing, field) for field in listing.__dataclass_fields__}
    values.update(overrides)
    return ParsedListing(**values)


def _fact(field: str, value: object, *, status: str = "usable", normalized_value: object | None = None):
    return build_property_fact_value(
        field=field,
        value=value,
        normalized_value=value if normalized_value is None else normalized_value,
        source="metadata",
        confidence=1.0,
        status=status,
        evidence_preview=str(value),
    )


def _record(index: int, *facts):
    url = f"https://kinmakelaars.nl/aanbod/wonen/breda/audit-{index}/kin-audit-{index:03d}"
    return build_property_facts_record(
        source_id="kinmakelaars.nl__breda",
        source_domain="kinmakelaars.nl",
        canonical_url=url,
        address_raw=f"Auditstraat {index}",
        city="Breda",
        status="beschikbaar",
        fetched_at="2026-06-27T00:00:00Z",
        expires_at="2026-07-11T00:00:00Z",
        facts=facts,
    )


def _full_record(index: int = 1):
    return _record(
        index,
        _fact("asking_price", 425000),
        _fact("property_type", "Tussenwoning", normalized_value="tussenwoning"),
        _fact("living_area_m2", 123),
        _fact("bedrooms", 3),
        _fact("energy_label", "A++"),
        _fact("eigendomssituatie", "Volle eigendom", normalized_value="volle_eigendom"),
    )


def _row(index: int, record=None, **listing_overrides: object):
    return build_kin_property_readiness_row(_listing(index, **listing_overrides), record or _full_record(index))


def _readiness(*rows, qa_clean_count: int | None = None, warnings: tuple[str, ...] = ()) -> KINFullPropertyReadinessResult:
    rows = tuple(rows)
    row_warnings = tuple(warning for row in rows for warning in row.warnings)
    all_warnings = tuple(dict.fromkeys((*warnings, *row_warnings)))
    return KINFullPropertyReadinessResult(
        source_id="kinmakelaars.nl__breda",
        source_domain="kinmakelaars.nl",
        listings_seen=qa_clean_count or len(rows),
        qa_clean_count=len(rows) if qa_clean_count is None else qa_clean_count,
        rows_built=len(rows),
        summaries_built=len(rows),
        active_count=len(rows),
        inactive_count=0,
        review_count=0,
        cache_hits=2,
        cache_misses=max(0, len(rows) - 2),
        detail_fetch_attempted=max(0, len(rows) - 2),
        detail_fetch_succeeded=max(0, len(rows) - 2),
        detail_fetch_failed=1 if "detail_fetch_exception" in all_warnings else 0,
        records_written=max(0, len(rows) - 2),
        location_usable_count=sum(1 for row in rows if row.location_status == "usable"),
        location_review_count=sum(1 for row in rows if row.location_status == "review"),
        location_missing_count=sum(1 for row in rows if row.location_status == "missing"),
        export_ready_count=sum(1 for row in rows if row.export_readiness == "export_ready"),
        export_review_count=sum(1 for row in rows if row.export_readiness == "export_review"),
        export_blocked_count=sum(1 for row in rows if row.export_readiness == "export_blocked"),
        field_completion_counts=(("asking_price", len(rows)),),
        missing_key_field_counts=_pairs(field for row in rows for field in row.missing_key_fields),
        attention_point_counts=_pairs(point for row in rows for point in row.attention_points),
        warning_counts=_pairs(all_warnings),
        sample_rows=rows[:5],
        rows=rows,
        warnings=all_warnings,
    )


def _pairs(values):
    counts: dict[str, int] = {}
    for value in values:
        if value:
            counts[value] = counts.get(value, 0) + 1
    return tuple(sorted(counts.items()))


def _gap(result, field: str):
    return next(gap for gap in result.field_gaps if gap.field == field)


def test_raises_value_error_when_cache_path_is_none() -> None:
    try:
        run_kin_full_coverage_completion_audit(config_path=CONFIG_FIXTURE, cache_path=None)  # type: ignore[arg-type]
    except ValueError as exc:
        assert str(exc) == "cache_path_required"
    else:
        raise AssertionError("expected ValueError")


def test_completed_true_when_rows_built_equals_qa_clean_count() -> None:
    result = build_kin_full_coverage_completion_result(_readiness(_row(1), _row(2)))

    assert result.completed is True
    assert result.partial is False


def test_partial_true_when_rows_built_less_than_qa_clean_count() -> None:
    result = build_kin_full_coverage_completion_result(_readiness(_row(1), qa_clean_count=2))

    assert result.completed is False
    assert result.partial is True
    assert "kin_coverage_incomplete" in result.warnings


def test_coverage_rate_computed_correctly() -> None:
    result = build_kin_full_coverage_completion_result(_readiness(_row(1), qa_clean_count=4))

    assert result.coverage_rate == 0.25


def test_runtime_exhausted_adds_warning() -> None:
    result = build_kin_full_coverage_completion_result(
        _readiness(_row(1), qa_clean_count=2, warnings=("kin_readiness_runtime_budget_exhausted",))
    )

    assert "kin_coverage_runtime_budget_exhausted" in result.warnings


def test_field_gaps_count_usable_review_missing_correctly() -> None:
    review_record = _record(
        2,
        _fact("asking_price", 425000),
        _fact("property_type", "Tussenwoning", status="review", normalized_value="tussenwoning"),
    )
    result = build_kin_full_coverage_completion_result(_readiness(_row(1), _row(2, review_record), _row(3, _record(3))))

    gap = _gap(result, "property_type")
    assert gap.usable_count == 1
    assert gap.review_count == 1
    assert gap.missing_count == 1
    assert gap.missing_rate == 0.3333


def test_location_gaps_include_missing_lat_lon_as_known_gap() -> None:
    result = build_kin_full_coverage_completion_result(_readiness(_row(1)))

    assert _gap(result, "latitude").missing_count == 1
    assert _gap(result, "longitude").missing_count == 1
    assert ("missing_coordinates", 1) in result.top_blockers


def test_top_blockers_aggregate_missing_key_fields() -> None:
    result = build_kin_full_coverage_completion_result(_readiness(_row(1, _record(1, _fact("asking_price", 425000)))))

    assert ("missing_key_field:property_type", 1) in result.top_blockers


def test_top_blockers_aggregate_attention_points() -> None:
    row = _row(1, _record(1, _fact("asking_price", 425000), _fact("property_type", "x", status="review")))
    result = build_kin_full_coverage_completion_result(_readiness(row))

    assert ("attention_point:property_type staat in review.", 1) in result.top_blockers


def test_problem_rows_max_ten() -> None:
    rows = tuple(_row(index, _record(index, _fact("asking_price", 425000))) for index in range(1, 13))
    result = build_kin_full_coverage_completion_result(_readiness(*rows))

    assert len(result.sample_problem_rows) == 10


def test_problem_rows_omit_html_json_long_descriptions_and_images() -> None:
    row = _row(
        1,
        _record(
            1,
            _fact("asking_price", 425000),
            _fact("property_type", "<html>raw</html>", status="review", normalized_value="tussenwoning"),
        ),
    )
    result = build_kin_full_coverage_completion_result(_readiness(row))

    text = repr(result.sample_problem_rows)
    assert "<html" not in text.casefold()
    assert '"docs"' not in text
    assert "photo.jpg" not in text
    assert len(text) < 2000


def test_uses_cache_hits_from_readiness_result() -> None:
    result = build_kin_full_coverage_completion_result(_readiness(_row(1), _row(2)))

    assert result.cache_hits == 2


def test_does_not_write_outside_explicit_cache_path(tmp_path: Path, monkeypatch) -> None:
    cache_path = tmp_path / "facts.jsonl"

    def fake_runner(**kwargs):
        assert kwargs["cache_path"] == cache_path
        return _readiness(_row(1))

    monkeypatch.setattr(audit_module, "run_kin_full_property_readiness", fake_runner)

    run_kin_full_coverage_completion_audit(config_path=CONFIG_FIXTURE, cache_path=cache_path)

    assert sorted(path.name for path in tmp_path.iterdir()) == []


def test_does_not_import_requests_httpx_playwright_selenium() -> None:
    disallowed = {"requests", "httpx", "playwright", "selenium"}
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    assert disallowed.isdisjoint({module.split(".")[0] for module in imported_modules})


def test_resume_strategy_can_progress_beyond_cached_first_rows(tmp_path: Path, monkeypatch) -> None:
    cache_path = tmp_path / "facts.jsonl"
    PropertyFactsCache(cache_path).upsert_many((_full_record(1), _full_record(2)))
    captured: dict[str, object] = {}

    def fake_runner(**kwargs):
        captured.update(kwargs)
        return _readiness(_row(1), _row(2), _row(3), qa_clean_count=3)

    monkeypatch.setattr(audit_module, "run_kin_full_property_readiness", fake_runner)

    result = run_kin_full_coverage_completion_audit(
        config_path=CONFIG_FIXTURE,
        cache_path=cache_path,
        max_details=1,
    )

    assert captured["max_details"] == 3
    assert result.completed is True


def test_quality_status_counts_are_reported() -> None:
    blocked = replace(_row(1, _record(1)), quality_status="insufficient_facts", export_readiness="export_blocked")
    result = build_kin_full_coverage_completion_result(_readiness(_row(2), blocked))

    assert result.client_ready_count == 1
    assert result.insufficient_facts_count == 1
