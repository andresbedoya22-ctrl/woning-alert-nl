from pathlib import Path
import csv
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.discovery.platform_fingerprint import (
    detect_platform_from_text,
    run_platform_fingerprint_audit,
)
from domek_wonen.discovery.website_fetcher import FetchResponse
from scripts.run_platform_fingerprint_audit import main as audit_main


class FakeFetcher:
    def __init__(self, *, timeout_seconds: float, delay_seconds: float) -> None:
        self.responses = {
            "https://alpha.nl": FetchResponse(
                url="https://alpha.nl",
                status_code=200,
                text="<html><script src='https://cdn.realworks.nl/app.js'></script></html>",
                content_type="text/html",
            ),
            "https://alpha.nl/aanbod": FetchResponse(
                url="https://alpha.nl/aanbod",
                status_code=200,
                text="<html>aanbod</html>",
                content_type="text/html",
            ),
            "https://beta.nl": FetchResponse(
                url="https://beta.nl",
                status_code=200,
                text="<html><meta name='generator' content='Kolibri CMS'></html>",
                content_type="text/html",
            ),
        }

    def fetch(self, url: str) -> FetchResponse:
        return self.responses.get(url, FetchResponse(url=url, error="not mocked"))

    def close(self) -> None:
        return None


def test_detects_realworks_from_html() -> None:
    platform, confidence, evidence = detect_platform_from_text("<html>realworks</html>", "")
    assert platform == "realworks"
    assert confidence >= 0.85
    assert "signal:realworks:realworks" in evidence


def test_detects_kolibri_from_html() -> None:
    platform, confidence, _evidence = detect_platform_from_text("<html>kolibri</html>", "")
    assert platform == "kolibri"
    assert confidence >= 0.85


def test_detects_skarabee_from_html() -> None:
    platform, confidence, _evidence = detect_platform_from_text("<html>skarabee</html>", "")
    assert platform == "skarabee"
    assert confidence >= 0.85


def test_detects_yes_co_from_html() -> None:
    platform, confidence, _evidence = detect_platform_from_text("<html>yes-co</html>", "")
    assert platform == "yes-co"
    assert confidence >= 0.85


def test_detects_wordpress_from_wp_signals() -> None:
    platform, confidence, evidence = detect_platform_from_text("<html>/wp-content/themes/site</html>", "wp-json")
    assert platform == "wordpress_makelaar_plugin"
    assert confidence >= 0.80
    assert any("signal:wordpress:wp-content" in item for item in evidence)


def test_detects_unknown_without_signals() -> None:
    platform, confidence, evidence = detect_platform_from_text("<html>hello world</html>", "")
    assert platform == "unknown"
    assert confidence < 0.5
    assert evidence == []


def test_script_generates_csv_and_summary(tmp_path: Path) -> None:
    input_path = tmp_path / "makelaar_sources_master.csv"
    input_path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website,gemeente,province,aanbod_url",
                "alpha__breda,Alpha,alpha.nl,https://alpha.nl,Breda,Noord-Brabant,https://alpha.nl/aanbod",
                "beta__breda,Beta,beta.nl,https://beta.nl,Breda,Noord-Brabant,",
            ]
        ),
        encoding="utf-8",
    )
    output_csv = tmp_path / "platform_fingerprint_results.csv"
    output_summary = tmp_path / "platform_fingerprint_summary.md"

    results = run_platform_fingerprint_audit(
        input_path=input_path,
        output_csv_path=output_csv,
        output_summary_path=output_summary,
        province="Noord-Brabant",
        max_sources=50,
        timeout_seconds=8.0,
        fetcher_factory=FakeFetcher,
    )

    assert len(results) == 2
    with output_csv.open("r", encoding="utf-8", newline="") as handle:
        written = list(csv.DictReader(handle))
    assert written[0]["detected_platform"] == "realworks"
    assert written[1]["detected_platform"] == "kolibri"

    summary = output_summary.read_text(encoding="utf-8")
    assert "Total sources analyzed: 2" in summary
    assert "realworks: 1" in summary
    assert "kolibri: 1" in summary
    assert "Next recommended parser to build:" in summary


def test_script_main_writes_default_outputs(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "makelaar_sources_master.csv"
    input_path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website,gemeente,province,aanbod_url",
                "alpha__breda,Alpha,alpha.nl,https://alpha.nl,Breda,Noord-Brabant,https://alpha.nl/aanbod",
            ]
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "data" / "discovery" / "platform_fingerprint"
    monkeypatch.setattr("scripts.run_platform_fingerprint_audit.DEFAULT_OUTPUT_DIR", output_dir)
    monkeypatch.setattr(
        "scripts.run_platform_fingerprint_audit.run_platform_fingerprint_audit",
        lambda **kwargs: run_platform_fingerprint_audit(fetcher_factory=FakeFetcher, **kwargs),
    )

    exit_code = audit_main(["--input", str(input_path), "--province", "Noord-Brabant"])

    assert exit_code == 0
    assert (output_dir / "platform_fingerprint_results.csv").exists()
    assert (output_dir / "platform_fingerprint_summary.md").exists()


def test_script_main_restores_latest_when_default_input_is_missing(tmp_path: Path, monkeypatch, capsys) -> None:
    latest_path = tmp_path / "data" / "discovery" / "latest" / "makelaar_sources_master.csv"
    valid_run = tmp_path / "data" / "discovery" / "runs" / "20260614T100000Z"
    valid_run.mkdir(parents=True, exist_ok=True)
    valid_run.joinpath("makelaar_sources_master.csv").write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website,gemeente,province,aanbod_url",
                "alpha__breda,Alpha,alpha.nl,https://alpha.nl,Breda,Noord-Brabant,https://alpha.nl/aanbod",
            ]
        ),
        encoding="utf-8",
    )
    valid_run.joinpath("discovered_sources.csv").write_text("source_id\nalpha__breda\n", encoding="utf-8")
    output_dir = tmp_path / "data" / "discovery" / "platform_fingerprint"
    monkeypatch.setattr(
        "domek_wonen.discovery.discovery_artifacts.DEFAULT_MAKELAAR_SOURCES_MASTER_PATH",
        latest_path,
    )
    monkeypatch.setattr("scripts.run_platform_fingerprint_audit.DEFAULT_OUTPUT_DIR", output_dir)
    monkeypatch.setattr(
        "scripts.run_platform_fingerprint_audit.run_platform_fingerprint_audit",
        lambda **kwargs: run_platform_fingerprint_audit(fetcher_factory=FakeFetcher, **kwargs),
    )

    exit_code = audit_main(["--province", "Noord-Brabant"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "restored discovery latest from run 20260614T100000Z" in captured.out
    assert latest_path.exists()
    assert (output_dir / "platform_fingerprint_results.csv").exists()
    assert (output_dir / "platform_fingerprint_summary.md").exists()
