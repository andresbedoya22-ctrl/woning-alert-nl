from pathlib import Path
import csv
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.discovery.platform_fingerprint import (
    TARGET_AREA_RESULT_FIELDNAMES,
    detect_target_platform_from_text,
    run_target_area_platform_fingerprint,
)
from domek_wonen.discovery.website_fetcher import FetchResponse
from scripts.run_target_area_platform_fingerprint import main as target_area_main


class FakeFetcher:
    def __init__(self, *, timeout_seconds: float, delay_seconds: float) -> None:
        self.responses = {
            "https://realworks-office.nl": FetchResponse(
                url="https://realworks-office.nl",
                status_code=200,
                text="<html>Welcome</html>",
                content_type="text/html",
            ),
            "https://realworks-office.nl/aanbod/woningaanbod": FetchResponse(
                url="https://realworks-office.nl/aanbod/woningaanbod",
                status_code=200,
                text="<html>woningaanbod</html>",
                content_type="text/html",
            ),
            "https://kinmakelaars.nl": FetchResponse(
                url="https://kinmakelaars.nl",
                status_code=200,
                text="<html>Website door OGonline</html>",
                content_type="text/html",
            ),
            "https://kinmakelaars.nl/aanbod/wonen/te-koop": FetchResponse(
                url="https://kinmakelaars.nl/aanbod/wonen/te-koop",
                status_code=200,
                text="<html>koopwoningen</html>",
                content_type="text/html",
            ),
            "https://wordpress-office.nl": FetchResponse(
                url="https://wordpress-office.nl",
                status_code=200,
                text="<html><link href='/wp-content/themes/site.css'></html>",
                content_type="text/html",
            ),
            "https://wordpress-office.nl/aanbod": FetchResponse(
                url="https://wordpress-office.nl/aanbod",
                status_code=200,
                text="<html>wp-json</html>",
                content_type="text/html",
            ),
        }

    def fetch(self, url: str) -> FetchResponse:
        return self.responses.get(url, FetchResponse(url=url, error="not mocked"))

    def close(self) -> None:
        return None


def test_detect_target_platform_detects_realworks_from_aanbod_path() -> None:
    platform, confidence, reasons = detect_target_platform_from_text(
        "",
        "",
        aanbod_url="https://realworks-office.nl/aanbod/woningaanbod",
    )
    assert platform == "realworks"
    assert confidence >= 0.85
    assert any("realworks" in reason for reason in reasons)


def test_detect_target_platform_detects_ogonline_from_branding() -> None:
    platform, confidence, reasons = detect_target_platform_from_text("<html>Website door OGonline</html>", "")
    assert platform == "ogonline_candidate"
    assert confidence >= 0.88
    assert "signal:ogonline:website_door_ogonline" in reasons


def test_detect_target_platform_detects_ogonline_from_aanbod_path() -> None:
    platform, confidence, reasons = detect_target_platform_from_text(
        "",
        "",
        aanbod_url="https://kinmakelaars.nl/aanbod/wonen/te-koop",
    )
    assert platform == "ogonline_candidate"
    assert confidence >= 0.75
    assert "signal:ogonline:aanbod_wonen_te_koop" in reasons


def test_detect_target_platform_detects_wordpress_candidate() -> None:
    platform, confidence, reasons = detect_target_platform_from_text("<html>/wp-content/themes/site</html>", "wp-json")
    assert platform == "wordpress_candidate"
    assert confidence >= 0.80
    assert any("signal:wordpress:wp-content" in reason for reason in reasons)


def test_target_area_run_generates_expected_csv_and_respects_gemeente_filter(tmp_path: Path) -> None:
    input_path = tmp_path / "makelaar_sources_master.csv"
    input_path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website,gemeente,province,aanbod_url",
                "rw__tilburg,Realworks Tilburg,realworks-office.nl,https://realworks-office.nl,Tilburg,Noord-Brabant,https://realworks-office.nl/aanbod/woningaanbod",
                "kin__waalwijk,KIN Waalwijk,kinmakelaars.nl,https://kinmakelaars.nl,Waalwijk,Noord-Brabant,https://kinmakelaars.nl/aanbod/wonen/te-koop",
                "wp__breda,WordPress Breda,wordpress-office.nl,https://wordpress-office.nl,Breda,Noord-Brabant,https://wordpress-office.nl/aanbod",
            ]
        ),
        encoding="utf-8",
    )

    run_id, results, inventory_path, report_path = run_target_area_platform_fingerprint(
        input_path=input_path,
        output_dir=tmp_path / "data" / "platform_fingerprint" / "target_area",
        target_gemeentes=["Tilburg", "Waalwijk"],
        max_sources=100,
        timeout_seconds=8.0,
        fetcher_factory=FakeFetcher,
    )

    assert run_id
    assert len(results) == 2
    assert {row["gemeente"] for row in results} == {"Tilburg", "Waalwijk"}
    assert inventory_path.exists()
    assert report_path.exists()

    with inventory_path.open("r", encoding="utf-8", newline="") as handle:
        written = list(csv.DictReader(handle))

    assert list(written[0].keys()) == TARGET_AREA_RESULT_FIELDNAMES
    assert written[0]["detected_platform"] == "realworks"
    assert written[0]["parser_status"] == "supported"
    assert written[0]["recommended_action"] == "use_existing_parser"
    assert written[1]["detected_platform"] == "ogonline_candidate"
    assert written[1]["recommended_action"] == "needs_parser"

    report_text = report_path.read_text(encoding="utf-8")
    assert "Total sources analyzed: 2" in report_text
    assert "Tilburg: 1" in report_text
    assert "Waalwijk: 1" in report_text
    assert "KIN Waalwijk (Waalwijk): ogonline_candidate" in report_text


def test_target_area_script_main_writes_default_outputs(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "makelaar_sources_master.csv"
    input_path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website,gemeente,province,aanbod_url",
                "kin__tilburg,KIN Tilburg,kinmakelaars.nl,https://kinmakelaars.nl,Tilburg,Noord-Brabant,https://kinmakelaars.nl/aanbod/wonen/te-koop",
            ]
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "data" / "platform_fingerprint" / "target_area"
    monkeypatch.setattr("scripts.run_target_area_platform_fingerprint.DEFAULT_OUTPUT_DIR", output_dir)
    monkeypatch.setattr(
        "scripts.run_target_area_platform_fingerprint.run_target_area_platform_fingerprint",
        lambda **kwargs: run_target_area_platform_fingerprint(fetcher_factory=FakeFetcher, **kwargs),
    )

    exit_code = target_area_main(["--input", str(input_path), "--target-gemeentes", "tilburg"])

    assert exit_code == 0
    run_dirs = [path for path in output_dir.iterdir() if path.is_dir()]
    assert len(run_dirs) == 1
    assert (run_dirs[0] / "target_area_platform_fingerprint_inventory.csv").exists()
    assert (run_dirs[0] / "target_area_platform_fingerprint_report.md").exists()
