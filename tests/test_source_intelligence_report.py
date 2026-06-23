from __future__ import annotations

from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.sources import build_source_intelligence_report, load_source_intelligence_csv
from domek_wonen.sources.source_intelligence_loader import build_source_intelligence_record


FIXTURE_PATH = Path("tests/fixtures/sources/source_intelligence_seed.csv")


def test_csv_fixture_loads_correctly() -> None:
    records = load_source_intelligence_csv(FIXTURE_PATH)
    assert len(records) == 12
    assert records[0].source_id == "realworks-seed"
    assert records[0].source_domain == "realworks-demo.nl"


def test_optional_columns_missing_do_not_break(tmp_path: Path) -> None:
    csv_path = tmp_path / "sources.csv"
    csv_path.write_text(
        "\n".join(
            [
                "source_name,homepage_url,aanbod_url,detected_platform,koop_signal",
                "Optional Source,https://www.optional-demo.nl,https://www.optional-demo.nl/aanbod,Realworks,yes",
            ]
        ),
        encoding="utf-8",
    )

    records = load_source_intelligence_csv(csv_path)

    assert len(records) == 1
    assert records[0].source_id.startswith("optional-demo-nl__na__")
    assert records[0].delivery_mode == "realworks_public"


def test_report_counts_by_statuses_and_modes() -> None:
    report = build_source_intelligence_report(load_source_intelligence_csv(FIXTURE_PATH))

    assert report["counts_by_aanbod_url_status"] == {"missing": 2, "suspect": 2, "valid": 8}
    assert report["counts_by_access_status"] == {
        "allowed": 8,
        "blocked": 2,
        "permission_required": 1,
        "researching": 1,
    }
    assert report["counts_by_delivery_mode"] == {
        "captcha_blocked": 1,
        "funda_iframe_blocked": 1,
        "json_ld": 1,
        "kolibri_public": 1,
        "ogonline_xhr": 1,
        "pararius_external_blocked": 1,
        "realworks_public": 1,
        "sitemap_detail": 1,
        "static_html_cards": 1,
        "unknown_manual_review": 1,
        "wordpress_html_cards": 1,
        "wordpress_rest": 1,
    }
    assert report["counts_by_parser_family_candidate"] == {
        "": 2,
        "iframe_blocked_handler": 2,
        "json_ld": 1,
        "kolibri_public": 1,
        "ogonline_xhr": 1,
        "realworks_public": 1,
        "sitemap_detail": 1,
        "static_html_cards": 1,
        "wordpress_html_cards": 1,
        "wordpress_rest": 1,
    }


def test_funda_and_pararius_mapping_respect_policy() -> None:
    records = {record.source_id: record for record in load_source_intelligence_csv(FIXTURE_PATH)}

    funda = records["funda-seed"]
    assert funda.delivery_mode == "funda_iframe_blocked"
    assert funda.parser_family_candidate == "iframe_blocked_handler"
    assert funda.recommended_action == "blocked_no_bypass"
    assert funda.access_status == "blocked"

    pararius = records["pararius-seed"]
    assert pararius.delivery_mode == "pararius_external_blocked"
    assert pararius.parser_family_candidate == "iframe_blocked_handler"
    assert pararius.recommended_action == "permission_required"
    assert pararius.access_status == "permission_required"


def test_blocking_signals_do_not_receive_normal_parser() -> None:
    blocked = {record.source_id: record for record in load_source_intelligence_csv(FIXTURE_PATH)}["blocked-seed"]

    assert blocked.delivery_mode == "captcha_blocked"
    assert blocked.parser_family_candidate == ""
    assert blocked.recommended_action == "blocked_no_bypass"


def test_platform_and_signal_mapping_rules() -> None:
    records = {record.source_id: record for record in load_source_intelligence_csv(FIXTURE_PATH)}

    assert records["realworks-seed"].delivery_mode == "realworks_public"
    assert records["ogonline-seed"].delivery_mode == "ogonline_xhr"
    assert records["kolibri-seed"].delivery_mode == "kolibri_public"
    assert records["wp-rest-seed"].delivery_mode == "wordpress_rest"
    assert records["wp-cards-seed"].delivery_mode == "wordpress_html_cards"
    assert records["static-seed"].delivery_mode == "static_html_cards"
    assert records["jsonld-seed"].delivery_mode == "json_ld"
    assert records["sitemap-seed"].delivery_mode == "sitemap_detail"
    assert records["unknown-seed"].delivery_mode == "unknown_manual_review"


def test_manual_review_queue_is_deterministically_ordered() -> None:
    report = build_source_intelligence_report(load_source_intelligence_csv(FIXTURE_PATH))
    queue = report["manual_review_queue"]

    assert [item["source_id"] for item in queue] == [
        "unknown-seed",
        "funda-seed",
        "pararius-seed",
        "blocked-seed",
    ]


def test_parser_family_priority_is_sorted() -> None:
    report = build_source_intelligence_report(load_source_intelligence_csv(FIXTURE_PATH))
    priorities = report["parser_family_priority"]

    assert [item["parser_family_candidate"] for item in priorities[:4]] == [
        "realworks_public",
        "ogonline_xhr",
        "wordpress_rest",
        "kolibri_public",
    ]


def test_missing_source_id_is_generated_deterministically() -> None:
    row = {
        "source_name": "Deterministic Demo",
        "homepage_url": "https://www.det-demo.nl",
        "aanbod_url": "https://www.det-demo.nl/aanbod",
        "gemeente": "Tilburg",
        "detected_platform": "Realworks",
    }

    first = build_source_intelligence_record(row)
    second = build_source_intelligence_record(row)

    assert first.source_id == second.source_id
    assert first.source_domain == "det-demo.nl"


def test_no_network_libraries_are_imported() -> None:
    module_text = Path("scraper/src/domek_wonen/sources/source_intelligence_loader.py").read_text(encoding="utf-8")
    script_text = Path("scripts/run_source_intelligence_report.py").read_text(encoding="utf-8")

    forbidden = ["requests", "httpx", "playwright", "selenium"]
    assert not any(token in module_text for token in forbidden)
    assert not any(token in script_text for token in forbidden)


def test_cli_writes_output_only_when_requested(tmp_path: Path) -> None:
    output_path = tmp_path / "report.json"
    command = [
        "py",
        "-3.12",
        "scripts/run_source_intelligence_report.py",
        "--input",
        str(FIXTURE_PATH),
        "--output",
        str(output_path),
    ]

    result = subprocess.run(command, capture_output=True, text=True, check=False)

    assert result.returncode == 0
    assert output_path.exists()
    assert "total_sources: 12" in result.stdout
    assert "manual review count: 4" in result.stdout
