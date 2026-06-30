from __future__ import annotations

import csv
from pathlib import Path

from openpyxl import load_workbook

from domek_wonen.sources.coverage_census import (
    CoverageCensusResult,
    CoverageSourceRecord,
    CoverageTerminalStatus,
    classify_family_from_content,
    compute_quality_metrics,
    consolidate_coverage_source_seeds,
    discover_aanbod_url,
    finalize_coverage_record,
    run_investigation_loop,
    run_noord_brabant_coverage_source_census,
    write_coverage_census_outputs,
)


def _row(**overrides: str) -> dict[str, str]:
    base = {
        "source_id": "alpha.nl__tilburg",
        "office_name": "Alpha Makelaars",
        "root_domain": "alpha.nl",
        "website": "https://www.alpha.nl",
        "gemeente": "Tilburg",
        "province": "Noord-Brabant",
        "aanbod_url": "https://www.alpha.nl/aanbod/woningaanbod",
        "aanbod_url_quality": "valid",
        "legal_status": "allowed_official_source",
        "evidence_file": "fixture.csv",
    }
    base.update(overrides)
    return base


def _record(**overrides: object) -> CoverageSourceRecord:
    base = {
        "source_id": "alpha.nl__tilburg",
        "source_name": "Alpha Makelaars",
        "domain": "alpha.nl",
        "root_url": "https://alpha.nl",
        "coverage_gemeente": "Tilburg",
        "coverage_province": "Noord-Brabant",
        "has_noord_brabant_coverage": True,
        "access_policy_status": "allowed",
    }
    base.update(overrides)
    return CoverageSourceRecord(**base)


def _fetcher(pages: dict[str, str]):
    def fetch(url: str) -> str:
        return pages[url.rstrip("/")]

    return fetch


def test_consolidates_local_source_seeds() -> None:
    records, duplicates = consolidate_coverage_source_seeds([_row(), _row(root_domain="beta.nl", source_id="beta.nl__breda")])
    assert len(records) == 2
    assert duplicates == []


def test_dedupes_by_normalized_domain() -> None:
    records, duplicates = consolidate_coverage_source_seeds([_row(root_domain="www.alpha.nl"), _row(source_id="alias", root_domain="alpha.nl")])
    assert len(records) == 1
    assert len(duplicates) == 1


def test_preserves_source_aliases() -> None:
    records, _duplicates = consolidate_coverage_source_seeds([_row(office_name="Alpha"), _row(source_id="alias", office_name="Alpha Alias")])
    assert "alias" in records[0].source_ids
    assert "Alpha Alias" in records[0].aliases


def test_includes_outside_office_source_if_it_has_noord_brabant_coverage() -> None:
    records, _ = consolidate_coverage_source_seeds([
        _row(office_province="Zuid-Holland", province="Noord-Brabant", gemeente="Tilburg")
    ])
    assert records[0].has_noord_brabant_coverage is True


def test_separates_office_location_from_coverage_location() -> None:
    records, _ = consolidate_coverage_source_seeds([
        _row(office_gemeente="Rotterdam", gemeente="Tilburg", office_province="Zuid-Holland", province="Noord-Brabant")
    ])
    assert records[0].office_gemeente == "Rotterdam"
    assert records[0].coverage_gemeente == "Tilburg"


def test_accepts_explicit_valid_aanbod_url_from_local_evidence() -> None:
    record = _record(aanbod_url="https://alpha.nl/woningen")
    assert discover_aanbod_url(record, fetch_text=None)
    assert record.aanbod_url_status == "accepted"


def test_rejects_property_detail_url_as_aanbod_url() -> None:
    record = _record(aanbod_url="https://alpha.nl/aanbod/woningaanbod/tilburg/koop/huis-123-main")
    assert not discover_aanbod_url(record, fetch_text=None)
    assert record.aanbod_url_candidates[0].rejection_reason == "property_detail_url_rejected"


def test_rejects_funda_pararius_as_operational_aanbod_url() -> None:
    record = _record(domain="alpha.nl", aanbod_url="https://www.funda.nl/koop/tilburg/")
    assert not discover_aanbod_url(record, fetch_text=None)
    assert record.aanbod_url_candidates[0].rejection_reason == "funda_pararius_not_operational"


def test_discovers_aanbod_url_from_homepage_link() -> None:
    record = _record(aanbod_url="")
    fetch = _fetcher({
        "https://alpha.nl": '<a href="/woningen">Koopwoningen</a>',
        "https://alpha.nl/woningen": '<div class="property-card">Vraagprijs</div>',
    })
    assert discover_aanbod_url(record, fetch_text=fetch, can_fetch=lambda _d, _p: True)
    assert record.aanbod_url == "https://alpha.nl/woningen"


def test_discovers_aanbod_url_from_sitemap() -> None:
    record = _record(aanbod_url="")
    fetch = _fetcher({
        "https://alpha.nl": "<html></html>",
        "https://alpha.nl/sitemap.xml": "<loc>https://alpha.nl/aanbod/woningaanbod</loc>",
    })
    assert discover_aanbod_url(record, fetch_text=fetch, can_fetch=lambda _d, _p: True)
    assert record.aanbod_url == "https://alpha.nl/aanbod/woningaanbod"


def test_discovers_aanbod_url_from_common_paths() -> None:
    record = _record(aanbod_url="")
    fetch = _fetcher({
        "https://alpha.nl": "<html></html>",
        "https://alpha.nl/sitemap.xml": "<urlset></urlset>",
        "https://alpha.nl/aanbod": '<article class="listing-card">k.k.</article>',
    })
    assert discover_aanbod_url(record, fetch_text=fetch, can_fetch=lambda _d, _p: True)
    assert record.aanbod_url == "https://alpha.nl/aanbod"


def test_marks_no_public_aanbod_after_exhausted_attempts() -> None:
    record = _record(aanbod_url="")
    run_investigation_loop(record, fetch_text=None)
    assert record.parser_family_candidate == "no_public_aanbod"
    assert record.terminal_status == CoverageTerminalStatus.CONFIRMED_NO_PUBLIC_AANBOD.value


def test_classifies_realworks_from_realworks_signals() -> None:
    family, _delivery, _confidence, signal = classify_family_from_content(content='<li class="aanbodEntry"></li>', url="/aanbod/woningaanbod")
    assert family == "realworks_public"
    assert signal == "realworks_signal"


def test_classifies_ogonline_from_xhr_api_signals() -> None:
    family, _delivery, _confidence, _signal = classify_family_from_content(content='{"docs":[],"totalDocs":0}')
    assert family == "ogonline_xhr"


def test_classifies_wordpress_from_wp_json_wp_content() -> None:
    assert classify_family_from_content(content="/wp-json/wp/v2")[0] == "wordpress_json"
    assert classify_family_from_content(content="/wp-content/themes/site")[0] == "wordpress_static"


def test_classifies_custom_html_from_server_rendered_listing_cards() -> None:
    assert classify_family_from_content(content='<div class="property-card">Vraagprijs k.k.</div>')[0] == "custom_html"


def test_classifies_custom_xhr_from_json_listing_payload_signals() -> None:
    assert classify_family_from_content(content="fetch('/api/listings')")[0] == "custom_xhr"


def test_classifies_custom_js_app_when_static_html_has_app_shell_but_no_listing_payload() -> None:
    assert classify_family_from_content(content='<div id="app"></div><script src="/main.js"></script>')[0] == "custom_js_app"


def test_marks_blocked_or_legal_review_when_access_policy_blocks() -> None:
    record = _record(access_policy_status="blocked")
    run_investigation_loop(record)
    assert record.parser_family_candidate == "blocked_or_legal_review"


def test_does_not_leave_final_parser_family_candidate_unknown() -> None:
    record = _record(aanbod_url="")
    run_investigation_loop(record)
    assert record.parser_family_candidate not in {"", "unknown", "missing", "tbd", "todo"}


def test_does_not_leave_missing_aanbod_url_without_terminal_reason() -> None:
    record = _record(aanbod_url="")
    run_investigation_loop(record)
    metrics = compute_quality_metrics(CoverageCensusResult(records=(record,), initial_source_count=1, deduped_source_count=1))
    assert metrics["missing_aanbod_url_without_terminal_reason_count"] == 0


def test_writes_workbook_with_all_required_sheets(tmp_path: Path) -> None:
    record = _record(aanbod_url="https://alpha.nl/woningen", parser_family_candidate="realworks_public", delivery_mode="realworks_public")
    run_investigation_loop(record)
    write_coverage_census_outputs(CoverageCensusResult(records=(record,), initial_source_count=1, deduped_source_count=1), tmp_path / "census.xlsx", tmp_path / "master.csv", tmp_path / "review.csv")
    workbook = load_workbook(tmp_path / "census.xlsx")
    try:
        assert workbook.sheetnames == [
            "Master Sources",
            "Aanbod URL Evidence",
            "Family Fingerprints",
            "Investigation Attempts",
            "Coverage Matrix",
            "Realworks Candidates",
            "OGonline Candidates",
            "Custom Needs Parser",
            "Blocked or Legal Review",
            "Duplicates",
            "Review Queue",
        ]
    finally:
        workbook.close()


def test_writes_review_queue(tmp_path: Path) -> None:
    record = _record(access_policy_status="blocked")
    run_investigation_loop(record)
    write_coverage_census_outputs(CoverageCensusResult(records=(record,), initial_source_count=1, deduped_source_count=1), tmp_path / "census.xlsx", tmp_path / "master.csv", tmp_path / "review.csv")
    with (tmp_path / "review.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["domain"] == "alpha.nl"
    assert rows[0]["terminal_status"] == CoverageTerminalStatus.CONFIRMED_BLOCKED_OR_LEGAL_REVIEW.value


def test_does_not_persist_raw_html_json(tmp_path: Path) -> None:
    record = _record(aanbod_url="https://alpha.nl/woningen", parser_family_candidate="custom_html", family_evidence="<html><script>raw</script></html>")
    run_investigation_loop(record)
    _wb, master, review = write_coverage_census_outputs(CoverageCensusResult(records=(record,), initial_source_count=1, deduped_source_count=1), tmp_path / "census.xlsx", tmp_path / "master.csv", tmp_path / "review.csv")
    text = master.read_text(encoding="utf-8") + review.read_text(encoding="utf-8")
    assert "<html" not in text
    assert "<script" not in text


def test_does_not_include_long_descriptions(tmp_path: Path) -> None:
    record = _record(aanbod_url="https://alpha.nl/woningen", parser_family_candidate="custom_html", coverage_evidence="x" * 900)
    run_investigation_loop(record)
    _wb, master, _review = write_coverage_census_outputs(CoverageCensusResult(records=(record,), initial_source_count=1, deduped_source_count=1), tmp_path / "census.xlsx", tmp_path / "master.csv", tmp_path / "review.csv")
    assert "x" * 600 not in master.read_text(encoding="utf-8")


def test_does_not_create_parser_per_makelaar() -> None:
    family, *_ = classify_family_from_content(content="Alpha Makelaars bespoke page")
    assert family in {"custom_js_app", "custom_html", "custom_xhr"}
    assert "alpha" not in family


def test_does_not_import_matching() -> None:
    import domek_wonen.sources.coverage_census as coverage_census

    assert "domek_wonen.matching" not in coverage_census.__dict__


def test_does_not_touch_funda_pararius_operationally() -> None:
    record = _record(aanbod_url="https://pararius.nl/koopwoningen/tilburg")
    run_investigation_loop(record)
    assert record.parser_family_candidate == "blocked_or_legal_review"


def test_quality_gate_fails_if_unknown_operational_family_remains() -> None:
    record = _record(parser_family_candidate="unknown", terminal_status="confirmed_source_ready")
    metrics = compute_quality_metrics(CoverageCensusResult(records=(record,), initial_source_count=1, deduped_source_count=1))
    assert metrics["operational_unknown_family_count"] == 1
    assert metrics["quality_gate_passed"] is False


def test_quality_gate_fails_if_missing_aanbod_url_lacks_terminal_reason() -> None:
    record = _record(aanbod_url="", parser_family_candidate="custom_html", terminal_status="confirmed_source_ready")
    metrics = compute_quality_metrics(CoverageCensusResult(records=(record,), initial_source_count=1, deduped_source_count=1))
    assert metrics["missing_aanbod_url_without_terminal_reason_count"] == 1
    assert metrics["quality_gate_passed"] is False


def test_runner_writes_outputs_from_local_csvs(tmp_path: Path) -> None:
    data_dir = tmp_path / "data" / "processed"
    data_dir.mkdir(parents=True)
    seed = data_dir / "sources_seed_noord_brabant.csv"
    seed.write_text(
        "source_id,office_name,root_domain,website,gemeente,province,aanbod_url,aanbod_url_quality,legal_status\n"
        "alpha.nl__tilburg,Alpha,alpha.nl,https://alpha.nl,Tilburg,Noord-Brabant,https://alpha.nl/woningen,valid,allowed_official_source\n",
        encoding="utf-8",
    )
    result = run_noord_brabant_coverage_source_census(
        repo_root=tmp_path,
        evidence_paths=(Path("data/processed/sources_seed_noord_brabant.csv"),),
        output_dir=tmp_path / "tmp" / "generated",
    )
    assert result.workbook_path and result.workbook_path.exists()
    assert result.master_csv_path and result.master_csv_path.exists()
    assert result.review_queue_csv_path and result.review_queue_csv_path.exists()
