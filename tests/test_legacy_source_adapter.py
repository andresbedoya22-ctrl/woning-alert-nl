from __future__ import annotations

from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.sources.legacy_source_adapter import (
    build_legacy_source_intelligence_report,
    load_legacy_source_records,
)


FIXTURE_PATH = Path("tests/fixtures/sources/legacy_source_master_seed.csv")


def test_load_legacy_source_records_loads_fixture() -> None:
    records = load_legacy_source_records(FIXTURE_PATH)

    assert len(records) == 10
    assert records[0].source_domain == "realworks-legacy.test"


def test_legacy_columns_map_to_source_intelligence_record() -> None:
    realworks = load_legacy_source_records(FIXTURE_PATH)[0]

    assert realworks.source_domain == "realworks-legacy.test"
    assert realworks.source_name == "Legacy Realworks"
    assert realworks.homepage_url == "https://www.realworks-legacy.test"
    assert realworks.aanbod_url == "https://www.realworks-legacy.test/koopwoningen"
    assert realworks.aanbod_url_status == "valid"
    assert realworks.detected_platform == "Realworks"
    assert realworks.evidence == "realworks public listing evidence"
    assert realworks.notes == "synthetic legacy master"


def test_missing_columns_do_not_break(tmp_path: Path) -> None:
    csv_path = tmp_path / "minimal.csv"
    csv_path.write_text(
        "makelaar_name,domain,website\nMinimal Source,https://www.minimal.test,https://minimal.test\n",
        encoding="utf-8",
    )

    records = load_legacy_source_records(csv_path)

    assert len(records) == 1
    assert records[0].source_name == "Minimal Source"
    assert records[0].source_domain == "minimal.test"
    assert records[0].source_id.startswith("minimal-test__na__")


def test_build_report_contains_all_layers() -> None:
    report = build_legacy_source_intelligence_report(FIXTURE_PATH)

    assert report["total_sources"] == 10
    assert report["unique_domains"] == 10
    assert "source_intelligence" in report
    assert "access_policy" in report
    assert "delivery_fingerprint" in report


def test_production_parser_ready_excludes_blocked_permission_and_manual_review() -> None:
    report = build_legacy_source_intelligence_report(FIXTURE_PATH)
    ready_ids = {item["source_id"] for item in report["production_parser_ready_sources"]}

    assert len(ready_ids) == 3
    assert all("blocked" not in source_id for source_id in ready_ids)
    assert all("pararius" not in source_id for source_id in ready_ids)
    assert all("unknown" not in source_id for source_id in ready_ids)


def test_funda_and_pararius_policy_mapping() -> None:
    report = build_legacy_source_intelligence_report(FIXTURE_PATH)

    blocked_domains = {item["source_domain"] for item in report["blocked_sources"]}
    permission_domains = {item["source_domain"] for item in report["permission_required_sources"]}

    assert "funda-wrapper-legacy.test" in blocked_domains
    assert "pararius-wrapper-legacy.test" in permission_domains


def test_realworks_and_ogonline_are_parser_family_candidates() -> None:
    report = build_legacy_source_intelligence_report(FIXTURE_PATH)
    candidates = {
        item["parser_family_candidate"]: item["source_count"]
        for item in report["top_parser_family_candidates"]
    }

    assert candidates["realworks_public"] == 1
    assert candidates["ogonline_xhr"] == 1


def test_manual_review_queue_exists() -> None:
    report = build_legacy_source_intelligence_report(FIXTURE_PATH)

    assert report["manual_review_queue"]
    assert any(item["source_domain"] == "unknown-legacy.test" for item in report["manual_review_queue"])


def test_adapter_and_cli_do_not_import_network_or_browser_libraries() -> None:
    module_text = Path("scraper/src/domek_wonen/sources/legacy_source_adapter.py").read_text(encoding="utf-8")
    script_text = Path("scripts/run_legacy_source_intelligence_report.py").read_text(encoding="utf-8")

    forbidden = ["requests", "httpx", "urllib.request", "playwright", "selenium"]
    assert not any(token in module_text for token in forbidden)
    assert not any(token in script_text for token in forbidden)


def test_cli_prints_summary_and_writes_only_when_requested(tmp_path: Path) -> None:
    output_path = tmp_path / "legacy-report.json"
    command = [
        "py",
        "-3.12",
        "scripts/run_legacy_source_intelligence_report.py",
        "--input",
        str(FIXTURE_PATH),
        "--output",
        str(output_path),
    ]

    result = subprocess.run(command, capture_output=True, text=True, check=False)

    assert result.returncode == 0
    assert output_path.exists()
    assert "total_sources: 10" in result.stdout
    assert "production_parser_ready_count: 3" in result.stdout
    assert "blocked_count: 2" in result.stdout
    assert "permission_required_count: 1" in result.stdout
