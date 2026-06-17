from __future__ import annotations

import csv
from pathlib import Path
import shutil
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.diagnostics.delivery_mode_fingerprint_audit import (
    detect_delivery_mode_from_text,
    run_delivery_mode_fingerprint_audit,
)
from domek_wonen.discovery.website_fetcher import FetchResponse
from domek_wonen.properties.source_parser_config import (
    load_json_file,
    validate_source_parser_config_file,
)
from scripts.run_delivery_mode_fingerprint_audit import main as audit_main


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "properties"


class FakeFetcher:
    def __init__(self, *, timeout_seconds: float, delay_seconds: float) -> None:
        del timeout_seconds
        del delay_seconds
        self.responses = {
            "https://realworks-office.nl": FetchResponse(
                url="https://realworks-office.nl",
                status_code=200,
                text="<html><script src='https://cdn.realworks.nl/app.js'></script></html>",
                content_type="text/html",
            ),
            "https://realworks-office.nl/aanbod/woningaanbod": FetchResponse(
                url="https://realworks-office.nl/aanbod/woningaanbod",
                status_code=200,
                text="<html>realworks woningen</html>",
                content_type="text/html",
            ),
            "https://kinmakelaars.nl": FetchResponse(
                url="https://kinmakelaars.nl",
                status_code=200,
                text=FIXTURES_DIR.joinpath("kin_ogonline_listing.html").read_text(encoding="utf-8"),
                content_type="text/html",
            ),
            "https://kinmakelaars.nl/aanbod/wonen/te-koop": FetchResponse(
                url="https://kinmakelaars.nl/aanbod/wonen/te-koop",
                status_code=200,
                text=FIXTURES_DIR.joinpath("kin_ogonline_listing.html").read_text(encoding="utf-8"),
                content_type="text/html",
            ),
            "https://static-cards.nl": FetchResponse(
                url="https://static-cards.nl",
                status_code=200,
                text=FIXTURES_DIR.joinpath("listing_page_with_3_cards.html").read_text(encoding="utf-8"),
                content_type="text/html",
            ),
            "https://static-cards.nl/aanbod": FetchResponse(
                url="https://static-cards.nl/aanbod",
                status_code=200,
                text=FIXTURES_DIR.joinpath("listing_page_with_3_cards.html").read_text(encoding="utf-8"),
                content_type="text/html",
            ),
            "https://wordpress-office.nl": FetchResponse(
                url="https://wordpress-office.nl",
                status_code=200,
                text=FIXTURES_DIR.joinpath("allround_listing_cards.html").read_text(encoding="utf-8"),
                content_type="text/html",
            ),
            "https://wordpress-office.nl/aanbod": FetchResponse(
                url="https://wordpress-office.nl/aanbod",
                status_code=200,
                text=FIXTURES_DIR.joinpath("allround_listing_cards.html").read_text(encoding="utf-8"),
                content_type="text/html",
            ),
            "https://funda-embed.nl": FetchResponse(
                url="https://funda-embed.nl",
                status_code=200,
                text="<html><iframe src='https://www.funda.nl/zoeken/koop'></iframe></html>",
                content_type="text/html",
            ),
            "https://funda-embed.nl/aanbod": FetchResponse(
                url="https://funda-embed.nl/aanbod",
                status_code=200,
                text="<html><iframe src='https://www.funda.nl/zoeken/koop'></iframe></html>",
                content_type="text/html",
            ),
            "https://unknown-office.nl": FetchResponse(
                url="https://unknown-office.nl",
                status_code=200,
                text="<html><body>Hello world</body></html>",
                content_type="text/html",
            ),
            "https://unknown-office.nl/aanbod": FetchResponse(
                url="https://unknown-office.nl/aanbod",
                status_code=200,
                text="<html><body>Hello world</body></html>",
                content_type="text/html",
            ),
        }

    def fetch(self, url: str) -> FetchResponse:
        return self.responses.get(url, FetchResponse(url=url, error="not mocked"))

    def close(self) -> None:
        return None


def _write_input_csv(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website,gemeente,province,aanbod_url",
                "realworks__tilburg,Realworks Office,realworks-office.nl,https://realworks-office.nl,Tilburg,Noord-Brabant,https://realworks-office.nl/aanbod/woningaanbod",
                "kin__tilburg,KIN Makelaars,kinmakelaars.nl,https://kinmakelaars.nl,Tilburg,Noord-Brabant,https://kinmakelaars.nl/aanbod/wonen/te-koop",
                "static__tilburg,Static Cards,static-cards.nl,https://static-cards.nl,Tilburg,Noord-Brabant,https://static-cards.nl/aanbod",
                "wp__tilburg,WordPress Cards,wordpress-office.nl,https://wordpress-office.nl,Tilburg,Noord-Brabant,https://wordpress-office.nl/aanbod",
                "funda__tilburg,Funda Embed,funda-embed.nl,https://funda-embed.nl,Tilburg,Noord-Brabant,https://funda-embed.nl/aanbod",
                "unknown__tilburg,Unknown Office,unknown-office.nl,https://unknown-office.nl,Tilburg,Noord-Brabant,https://unknown-office.nl/aanbod"
            ]
        ),
        encoding="utf-8",
    )


def _write_platform_fingerprint_csv(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website_url,aanbod_url,detected_platform,confidence,evidence,parser_priority,recommended_next_action,fetch_status,error",
                "realworks__tilburg,Realworks Office,realworks-office.nl,https://realworks-office.nl,https://realworks-office.nl/aanbod/woningaanbod,realworks,0.98,signal:realworks,p1,keep,homepage_ok,",
                "kin__tilburg,KIN Makelaars,kinmakelaars.nl,https://kinmakelaars.nl,https://kinmakelaars.nl/aanbod/wonen/te-koop,ogonline_candidate,0.95,signal:ogonline,p1,keep,homepage_ok,",
                "static__tilburg,Static Cards,static-cards.nl,https://static-cards.nl,https://static-cards.nl/aanbod,unknown,0.20,,p4,review,homepage_ok,",
                "wp__tilburg,WordPress Cards,wordpress-office.nl,https://wordpress-office.nl,https://wordpress-office.nl/aanbod,wordpress_candidate,0.85,signal:wordpress,p2,review,homepage_ok,",
                "funda__tilburg,Funda Embed,funda-embed.nl,https://funda-embed.nl,https://funda-embed.nl/aanbod,unknown,0.20,,p4,review,homepage_ok,",
                "unknown__tilburg,Unknown Office,unknown-office.nl,https://unknown-office.nl,https://unknown-office.nl/aanbod,unknown,0.20,,p4,review,homepage_ok,"
            ]
        ),
        encoding="utf-8",
    )


def _make_workspace_tmp_dir() -> Path:
    path = Path("tmp") / f"delivery-mode-tests-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def test_realworks_source_classified_as_realworks() -> None:
    mode, confidence, _evidence = detect_delivery_mode_from_text(
        "<html><script src='https://cdn.realworks.nl/app.js'></script></html>",
        "<html>realworks</html>",
        listing_url="https://realworks-office.nl/aanbod/woningaanbod",
    )
    assert mode == "realworks"
    assert confidence >= 0.95


def test_kin_source_classified_as_ogonline_xhr() -> None:
    html = FIXTURES_DIR.joinpath("kin_ogonline_listing.html").read_text(encoding="utf-8")
    mode, confidence, evidence = detect_delivery_mode_from_text(
        html,
        html,
        website_url="https://kinmakelaars.nl",
        listing_url="https://kinmakelaars.nl/aanbod/wonen/te-koop",
    )
    assert mode == "ogonline_xhr"
    assert confidence >= 0.90
    assert evidence


def test_html_card_source_classified_as_html_static_cards_when_cards_visible() -> None:
    html = FIXTURES_DIR.joinpath("listing_page_with_3_cards.html").read_text(encoding="utf-8")
    mode, confidence, evidence = detect_delivery_mode_from_text(
        html,
        html,
        website_url="https://static-cards.nl",
        listing_url="https://static-cards.nl/aanbod",
    )
    assert mode == "html_static_cards"
    assert confidence >= 0.68
    assert any("detail_links" in item for item in evidence)


def test_wordpress_source_classified_as_wordpress_cards_when_wp_signals_and_cards_visible() -> None:
    html = FIXTURES_DIR.joinpath("allround_listing_cards.html").read_text(encoding="utf-8")
    mode, confidence, evidence = detect_delivery_mode_from_text(
        html,
        html,
        website_url="https://wordpress-office.nl",
        listing_url="https://wordpress-office.nl/aanbod",
    )
    assert mode == "wordpress_cards"
    assert confidence >= 0.80
    assert any("signal:wordpress" in item for item in evidence)


def test_funda_iframe_classified_as_iframe_funda_blocked() -> None:
    mode, confidence, _evidence = detect_delivery_mode_from_text(
        "<html><iframe src='https://www.funda.nl/zoeken/koop'></iframe></html>",
        "",
        website_url="https://funda-embed.nl",
        listing_url="https://funda-embed.nl/aanbod",
    )
    assert mode == "iframe_funda_blocked"
    assert confidence >= 0.95


def test_unknown_low_confidence_source_classified_as_unknown_manual_review() -> None:
    mode, confidence, _evidence = detect_delivery_mode_from_text(
        "<html><body>Hello world</body></html>",
        "<html><body>Hello world</body></html>",
        website_url="https://unknown-office.nl",
        listing_url="https://unknown-office.nl/aanbod",
    )
    assert mode == "unknown_manual_review"
    assert confidence <= 0.30


def test_config_schema_examples_validate() -> None:
    schema = load_json_file(Path("data/config/source_parser_configs/schema_v1.json"))
    assert "required_fields" in schema
    html_result = validate_source_parser_config_file(Path("data/config/source_parser_configs/html_static_cards.example.json"))
    wordpress_result = validate_source_parser_config_file(Path("data/config/source_parser_configs/wordpress_cards.example.json"))
    assert html_result.ok, html_result.errors
    assert wordpress_result.ok, wordpress_result.errors


def test_audit_generates_timestamped_outputs() -> None:
    base_dir = _make_workspace_tmp_dir()
    try:
        input_path = base_dir / "makelaar_sources_master.csv"
        fingerprint_path = base_dir / "platform_fingerprint_results.csv"
        output_dir = base_dir / "delivery_mode_fingerprint"
        _write_input_csv(input_path)
        _write_platform_fingerprint_csv(fingerprint_path)

        result = run_delivery_mode_fingerprint_audit(
            city="Tilburg",
            province="Noord-Brabant",
            input_path=input_path,
            platform_fingerprint_path=fingerprint_path,
            output_base_dir=output_dir,
            fetcher_factory=FakeFetcher,
        )

        assert result.report_path.exists()
        assert result.inventory_path.exists()

        with result.inventory_path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        assert len(rows) == 6
        assert {row["detected_delivery_mode"] for row in rows} >= {
            "realworks",
            "ogonline_xhr",
            "html_static_cards",
            "wordpress_cards",
            "iframe_funda_blocked",
            "unknown_manual_review",
        }

        report_text = result.report_path.read_text(encoding="utf-8")
        assert "Counts By Delivery Mode" in report_text
        assert "Top HTML Static Card Config Candidates" in report_text
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)


def test_cli_main_prints_run_outputs() -> None:
    base_dir = _make_workspace_tmp_dir()
    try:
        input_path = base_dir / "makelaar_sources_master.csv"
        fingerprint_path = base_dir / "platform_fingerprint_results.csv"
        output_dir = base_dir / "delivery_mode_fingerprint"
        _write_input_csv(input_path)
        _write_platform_fingerprint_csv(fingerprint_path)

        from scripts import run_delivery_mode_fingerprint_audit as cli_module

        original_runner = cli_module.run_delivery_mode_fingerprint_audit
        try:
            cli_module.run_delivery_mode_fingerprint_audit = lambda **kwargs: run_delivery_mode_fingerprint_audit(  # type: ignore[assignment]
                fetcher_factory=FakeFetcher,
                output_base_dir=output_dir,
                **kwargs,
            )
            exit_code = audit_main(
                [
                    "--city",
                    "Tilburg",
                    "--province",
                    "Noord-Brabant",
                    "--input",
                    str(input_path),
                    "--platform-fingerprint-input",
                    str(fingerprint_path),
                ]
            )
        finally:
            cli_module.run_delivery_mode_fingerprint_audit = original_runner  # type: ignore[assignment]

        assert exit_code == 0
        run_dirs = [path for path in output_dir.iterdir() if path.is_dir()]
        assert run_dirs
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)
