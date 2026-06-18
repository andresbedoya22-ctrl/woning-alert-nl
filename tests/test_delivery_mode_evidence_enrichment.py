from __future__ import annotations

import csv
from pathlib import Path
import shutil
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.diagnostics.delivery_mode_evidence_enrichment import (
    detect_enriched_delivery_mode,
    run_delivery_mode_evidence_enrichment,
)
from domek_wonen.discovery.website_fetcher import FetchResponse
from scripts.run_delivery_mode_evidence_enrichment import main as enrichment_main


class FakeFetcher:
    def __init__(self, *, timeout_seconds: float, delay_seconds: float) -> None:
        del timeout_seconds
        del delay_seconds
        self.responses = {
            "https://architectuurmakelaar.nl": FetchResponse(
                url="https://architectuurmakelaar.nl",
                status_code=200,
                text="""
                    <html>
                        <body>
                            <a href="/aanbod">Aanbod</a>
                        </body>
                    </html>
                """,
                content_type="text/html",
            ),
            "https://architectuurmakelaar.nl/aanbod": FetchResponse(
                url="https://architectuurmakelaar.nl/aanbod",
                status_code=200,
                text="""
                    <html>
                        <div class="listing-card woning-card">
                            <a href="/aanbod/woning/123-tilburg">Go</a>
                            <span>Ringbaan Oost 10</span>
                            <span>€ 395.000 k.k.</span>
                            <span>Tilburg</span>
                            <span>110 m2</span>
                            <span>5 kamers</span>
                        </div>
                    </html>
                """,
                content_type="text/html",
            ),
            "https://architectuurmakelaar.nl/aanbod/woning/123-tilburg": FetchResponse(
                url="https://architectuurmakelaar.nl/aanbod/woning/123-tilburg",
                status_code=200,
                text="<html><body>Ringbaan Oost 10 Tilburg € 395.000 k.k. 110 m2 5 kamers</body></html>",
                content_type="text/html",
            ),
            "https://debontmakelaardij.nl": FetchResponse(
                url="https://debontmakelaardij.nl",
                status_code=200,
                text="""
                    <html>
                        <body>
                            <a href="/woningaanbod">Woningaanbod</a>
                            <script src="/wp-content/theme.js"></script>
                            <link rel="https://api.w.org/" href="/wp-json/" />
                        </body>
                    </html>
                """,
                content_type="text/html",
            ),
            "https://debontmakelaardij.nl/woningaanbod": FetchResponse(
                url="https://debontmakelaardij.nl/woningaanbod",
                status_code=200,
                text="""
                    <html>
                        <div class="property-card">
                            <a href="/woningaanbod/tilburg/besterdstraat-12">Go</a>
                            <span>Besterdstraat 12</span>
                            <span>€ 320.000 k.k.</span>
                            <span>Tilburg</span>
                        </div>
                    </html>
                """,
                content_type="text/html",
            ),
            "https://debontmakelaardij.nl/woningaanbod/tilburg/besterdstraat-12": FetchResponse(
                url="https://debontmakelaardij.nl/woningaanbod/tilburg/besterdstraat-12",
                status_code=200,
                text="<html><body>Besterdstraat 12 Tilburg € 320.000 k.k.</body></html>",
                content_type="text/html",
            ),
            "https://hendriks.nl": FetchResponse(
                url="https://hendriks.nl",
                status_code=200,
                text="<html><body><a href='/wonen'>Wonen</a></body></html>",
                content_type="text/html",
            ),
            "https://hendriks.nl/wonen": FetchResponse(
                url="https://hendriks.nl/wonen",
                status_code=200,
                text="""
                    <html>
                        <script type="application/ld+json">
                            {"@type":"Residence","offers":{"price":"350000"},"address":{"@type":"PostalAddress","addressLocality":"Tilburg"}}
                        </script>
                    </html>
                """,
                content_type="text/html",
            ),
            "https://huijsmansmakelaardij.nl": FetchResponse(
                url="https://huijsmansmakelaardij.nl",
                status_code=200,
                text="<html><body><a href='/aanbod'>Aanbod</a></body></html>",
                content_type="text/html",
            ),
            "https://huijsmansmakelaardij.nl/aanbod": FetchResponse(
                url="https://huijsmansmakelaardij.nl/aanbod",
                status_code=200,
                text="""
                    <html>
                        <script>
                            fetch('/api/woningen')
                        </script>
                    </html>
                """,
                content_type="text/html",
            ),
            "https://kamerbemiddelingtilburg.nl": FetchResponse(
                url="https://kamerbemiddelingtilburg.nl",
                status_code=200,
                text="<html><body><iframe src='https://www.funda.nl/zoeken/koop'></iframe></body></html>",
                content_type="text/html",
            ),
            "https://kernmakelaars.nl": FetchResponse(
                url="https://kernmakelaars.nl",
                status_code=200,
                text="<html><body>bedrijfsmakelaar bedrijfsruimte kantoorruimte nieuwbouwproject</body></html>",
                content_type="text/html",
            ),
            "https://lemmens.nl": FetchResponse(
                url="https://lemmens.nl",
                status_code=200,
                text="<html><body>Hello</body></html>",
                content_type="text/html",
            ),
            "https://hrs.nl": FetchResponse(
                url="https://hrs.nl",
                status_code=200,
                text="<html><body><a href='/diensten/verkoop'>Verkoop</a></body></html>",
                content_type="text/html",
            ),
            "https://hrs.nl/diensten/verkoop": FetchResponse(
                url="https://hrs.nl/diensten/verkoop",
                status_code=403,
                text="",
                content_type="text/html",
            ),
        }

    def fetch(self, url: str) -> FetchResponse:
        return self.responses.get(url, FetchResponse(url=url, error="not mocked"))

    def extract_internal_links(self, base_url: str, html: str) -> list[str]:
        del html
        mapping = {
            "https://architectuurmakelaar.nl": ["https://architectuurmakelaar.nl/aanbod"],
            "https://debontmakelaardij.nl": ["https://debontmakelaardij.nl/woningaanbod"],
            "https://hendriks.nl": ["https://hendriks.nl/wonen"],
            "https://huijsmansmakelaardij.nl": ["https://huijsmansmakelaardij.nl/aanbod"],
            "https://hrs.nl": ["https://hrs.nl/diensten/verkoop"],
        }
        return mapping.get(base_url.rstrip("/"), [])

    def close(self) -> None:
        return None


def _make_workspace_tmp_dir() -> Path:
    path = Path("tmp") / f"delivery-mode-evidence-tests-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def _write_source_master(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website,gemeente,province,aanbod_url",
                "architectuurmakelaar.nl__tilburg,Architectuurmakelaar,architectuurmakelaar.nl,https://architectuurmakelaar.nl,Tilburg,Noord-Brabant,https://architectuurmakelaar.nl/aanbod",
                "debontmakelaardij.nl__tilburg,De Bont Makelaardij B.V.,debontmakelaardij.nl,https://debontmakelaardij.nl,Tilburg,Noord-Brabant,https://debontmakelaardij.nl/woningaanbod",
                "hendriks.nl__tilburg,Hendriks Makelaardij Tilburg,hendriks.nl,https://hendriks.nl,Tilburg,Noord-Brabant,https://hendriks.nl/wonen",
                "huijsmansmakelaardij.nl__tilburg,Huijsmans Makelaardij,huijsmansmakelaardij.nl,https://huijsmansmakelaardij.nl,Tilburg,Noord-Brabant,https://huijsmansmakelaardij.nl/aanbod",
                "kamerbemiddelingtilburg.nl__tilburg,Kamerbemiddeling Tilburg,kamerbemiddelingtilburg.nl,https://kamerbemiddelingtilburg.nl,Tilburg,Noord-Brabant,",
                "kernmakelaars.nl__tilburg,Kern Makelaars Tilburg B.V.,kernmakelaars.nl,https://kernmakelaars.nl,Tilburg,Noord-Brabant,",
                "lemmens.nl__tilburg,Lemmens Makelaardij B.V.,lemmens.nl,https://lemmens.nl,Tilburg,Noord-Brabant,",
                "hrs.nl__tilburg,M&S powered bij HRS,hrs.nl,https://hrs.nl,Tilburg,Noord-Brabant,"
            ]
        ),
        encoding="utf-8",
    )


def _write_platform_fingerprint(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website_url,aanbod_url,detected_platform,confidence,evidence,parser_priority,recommended_next_action,fetch_status,error",
                "architectuurmakelaar.nl__tilburg,Architectuurmakelaar,architectuurmakelaar.nl,https://architectuurmakelaar.nl,https://architectuurmakelaar.nl/aanbod,custom,0.55,,p3,manual_review,homepage_ok,",
                "debontmakelaardij.nl__tilburg,De Bont Makelaardij B.V.,debontmakelaardij.nl,https://debontmakelaardij.nl,https://debontmakelaardij.nl/woningaanbod,custom,0.55,,p3,manual_review,homepage_ok,",
                "hendriks.nl__tilburg,Hendriks Makelaardij Tilburg,hendriks.nl,https://hendriks.nl,https://hendriks.nl/wonen,custom,0.55,,p3,manual_review,homepage_ok,",
                "huijsmansmakelaardij.nl__tilburg,Huijsmans Makelaardij,huijsmansmakelaardij.nl,https://huijsmansmakelaardij.nl,https://huijsmansmakelaardij.nl/aanbod,custom,0.55,,p3,manual_review,homepage_ok,",
                "kamerbemiddelingtilburg.nl__tilburg,Kamerbemiddeling Tilburg,kamerbemiddelingtilburg.nl,https://kamerbemiddelingtilburg.nl,,custom,0.55,,p3,manual_review,homepage_ok,",
                "kernmakelaars.nl__tilburg,Kern Makelaars Tilburg B.V.,kernmakelaars.nl,https://kernmakelaars.nl,,custom,0.55,,p3,manual_review,homepage_ok,",
                "lemmens.nl__tilburg,Lemmens Makelaardij B.V.,lemmens.nl,https://lemmens.nl,,custom,0.55,,p3,manual_review,homepage_ok,",
                "hrs.nl__tilburg,M&S powered bij HRS,hrs.nl,https://hrs.nl,,custom,0.55,,p3,manual_review,homepage_ok,"
            ]
        ),
        encoding="utf-8",
    )


def _write_delivery_mode_inventory(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "source_domain,source_name,current_platform_guess,detected_delivery_mode,confidence,parser_family_candidate,config_required,likely_reusable_template,evidence,recommended_next_action",
                "architectuurmakelaar.nl,Architectuurmakelaar,custom,unknown_manual_review,0.25,,,,,manual_review_needed",
                "debontmakelaardij.nl,De Bont Makelaardij B.V.,custom,unknown_manual_review,0.25,,,,,manual_review_needed",
                "hendriks.nl,Hendriks Makelaardij Tilburg,custom,unknown_manual_review,0.25,,,,,manual_review_needed",
                "huijsmansmakelaardij.nl,Huijsmans Makelaardij,custom,unknown_manual_review,0.25,,,,,manual_review_needed",
                "kamerbemiddelingtilburg.nl,Kamerbemiddeling Tilburg,custom,unknown_manual_review,0.25,,,,,manual_review_needed",
                "kernmakelaars.nl,Kern Makelaars Tilburg B.V.,custom,unknown_manual_review,0.25,,,,,manual_review_needed",
                "lemmens.nl,Lemmens Makelaardij B.V.,custom,unknown_manual_review,0.25,,,,,manual_review_needed",
                "hrs.nl,M&S powered bij HRS,custom,unknown_manual_review,0.25,,,,,manual_review_needed"
            ]
        ),
        encoding="utf-8",
    )


def test_wordpress_html_with_cards_classified_as_wordpress_cards() -> None:
    signals = detect_enriched_delivery_mode(
        homepage_html="<html><script src='/wp-content/theme.js'></script><a href='/aanbod'>Aanbod</a></html>",
        listing_html="<html><div class='property-card'><a href='/aanbod/woning/1'>Go</a> Besterdstraat 12 € 320.000 k.k. Tilburg</div></html>",
        detail_html="",
        website_url="https://debontmakelaardij.nl",
        listing_url="https://debontmakelaardij.nl/aanbod",
        detail_url="",
        city="Tilburg",
    )
    assert signals.detected_delivery_mode_enriched == "wordpress_cards"


def test_plain_html_cards_classified_as_html_static_cards() -> None:
    signals = detect_enriched_delivery_mode(
        homepage_html="<html><a href='/aanbod'>Aanbod</a></html>",
        listing_html="<html><div class='listing-card'><a href='/aanbod/woning/1'>Go</a> Ringbaan Oost 10 € 395.000 k.k. Tilburg 110 m2 5 kamers</div></html>",
        detail_html="",
        website_url="https://architectuurmakelaar.nl",
        listing_url="https://architectuurmakelaar.nl/aanbod",
        detail_url="",
        city="Tilburg",
    )
    assert signals.detected_delivery_mode_enriched == "html_static_cards"


def test_json_ld_only_classified_as_json_ld() -> None:
    signals = detect_enriched_delivery_mode(
        homepage_html="",
        listing_html="""
            <html>
                <script type='application/ld+json'>
                    {"@type":"Residence","offers":{"price":"350000"},"address":{"@type":"PostalAddress","addressLocality":"Tilburg"}}
                </script>
            </html>
        """,
        detail_html="",
        website_url="https://hendriks.nl",
        listing_url="https://hendriks.nl/wonen",
        detail_url="",
        city="Tilburg",
    )
    assert signals.detected_delivery_mode_enriched == "json_ld"


def test_xhr_signal_classified_as_xhr_api() -> None:
    signals = detect_enriched_delivery_mode(
        homepage_html="",
        listing_html="<html><script>fetch('/api/woningen')</script></html>",
        detail_html="",
        website_url="https://huijsmansmakelaardij.nl",
        listing_url="https://huijsmansmakelaardij.nl/aanbod",
        detail_url="",
        city="Tilburg",
    )
    assert signals.detected_delivery_mode_enriched == "xhr_api"


def test_funda_iframe_classified_as_iframe_blocked() -> None:
    signals = detect_enriched_delivery_mode(
        homepage_html="<html><iframe src='https://www.funda.nl/zoeken/koop'></iframe></html>",
        listing_html="",
        detail_html="",
        website_url="https://kamerbemiddelingtilburg.nl",
        listing_url="",
        detail_url="",
        city="Tilburg",
    )
    assert signals.detected_delivery_mode_enriched == "iframe_funda_blocked"


def test_commercial_wording_only_classified_as_commercial_only() -> None:
    signals = detect_enriched_delivery_mode(
        homepage_html="<html><body>bedrijfsmakelaar bedrijfsruimte kantoorruimte nieuwbouwproject</body></html>",
        listing_html="",
        detail_html="",
        website_url="https://kernmakelaars.nl",
        listing_url="",
        detail_url="",
        city="Tilburg",
    )
    assert signals.detected_delivery_mode_enriched == "commercial_only"


def test_no_listing_found_result_is_emitted_by_runner() -> None:
    base_dir = _make_workspace_tmp_dir()
    try:
        source_master = base_dir / "makelaar_sources_master.csv"
        platform_fingerprint = base_dir / "platform_fingerprint_results.csv"
        delivery_inventory = base_dir / "delivery_mode_inventory.csv"
        output_dir = base_dir / "delivery_mode_evidence"
        _write_source_master(source_master)
        _write_platform_fingerprint(platform_fingerprint)
        _write_delivery_mode_inventory(delivery_inventory)

        result = run_delivery_mode_evidence_enrichment(
            city="Tilburg",
            province="Noord-Brabant",
            input_path=source_master,
            platform_fingerprint_path=platform_fingerprint,
            delivery_mode_inventory_path=delivery_inventory,
            output_base_dir=output_dir,
            fetcher_factory=FakeFetcher,
        )

        rows_by_domain = {row["source_domain"]: row for row in result.inventory_rows}
        assert rows_by_domain["lemmens.nl"]["detected_delivery_mode_enriched"] == "no_listing_found"
        assert rows_by_domain["architectuurmakelaar.nl"]["detected_delivery_mode_enriched"] == "html_static_cards"
        assert rows_by_domain["debontmakelaardij.nl"]["detected_delivery_mode_enriched"] == "wordpress_cards"
        assert rows_by_domain["hendriks.nl"]["detected_delivery_mode_enriched"] == "json_ld"
        assert rows_by_domain["huijsmansmakelaardij.nl"]["detected_delivery_mode_enriched"] == "xhr_api"
        assert rows_by_domain["kamerbemiddelingtilburg.nl"]["detected_delivery_mode_enriched"] == "iframe_funda_blocked"
        assert rows_by_domain["kernmakelaars.nl"]["detected_delivery_mode_enriched"] == "commercial_only"
        assert result.report_path.exists()
        assert result.inventory_path.exists()
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)


def test_cli_main_prints_run_outputs() -> None:
    base_dir = _make_workspace_tmp_dir()
    try:
        source_master = base_dir / "makelaar_sources_master.csv"
        platform_fingerprint = base_dir / "platform_fingerprint_results.csv"
        delivery_inventory = base_dir / "delivery_mode_inventory.csv"
        output_dir = base_dir / "delivery_mode_evidence"
        _write_source_master(source_master)
        _write_platform_fingerprint(platform_fingerprint)
        _write_delivery_mode_inventory(delivery_inventory)

        from scripts import run_delivery_mode_evidence_enrichment as cli_module

        original_runner = cli_module.run_delivery_mode_evidence_enrichment
        try:
            cli_module.run_delivery_mode_evidence_enrichment = lambda **kwargs: run_delivery_mode_evidence_enrichment(  # type: ignore[assignment]
                fetcher_factory=FakeFetcher,
                output_base_dir=output_dir,
                **kwargs,
            )
            exit_code = enrichment_main(
                [
                    "--city",
                    "Tilburg",
                    "--province",
                    "Noord-Brabant",
                    "--input",
                    str(source_master),
                    "--platform-fingerprint-input",
                    str(platform_fingerprint),
                    "--delivery-mode-inventory-input",
                    str(delivery_inventory),
                ]
            )
        finally:
            cli_module.run_delivery_mode_evidence_enrichment = original_runner  # type: ignore[assignment]

        assert exit_code == 0
        run_dirs = [path for path in output_dir.iterdir() if path.is_dir()]
        assert run_dirs
        with (run_dirs[0] / "delivery_mode_evidence_inventory.csv").open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        assert rows
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)
