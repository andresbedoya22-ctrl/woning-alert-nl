from __future__ import annotations

import csv
import importlib.util
from pathlib import Path
import socket
import subprocess
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.portals.adapters import funda, huislijn, pararius
from domek_wonen.portals.live_fetch import FetchResult
from domek_wonen.portals.models import PortalListing, PortalMode, PortalSpikeResult, SourceStatus
from domek_wonen.portals.portal_inventory_spike import (
    calculate_duplicate_url_rate,
    calculate_fill_rate,
    dedup_key_for_listing,
    detect_blocked_page,
    generate_markdown_report,
    summarize_city_result,
    write_csv_outputs,
)


def _load_runner_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_portal_inventory_spike.py"
    spec = importlib.util.spec_from_file_location("run_portal_inventory_spike", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RUNNER = _load_runner_module()

HUISLIJN_SAMPLE = """
<article class="listing-card" data-url="https://www.huislijn.nl/koopwoning/nederland/tilburg/1234567/test-huis">
  <a class="listing-link" href="https://www.huislijn.nl/koopwoning/nederland/tilburg/1234567/test-huis">Bekijk</a>
  <div class="address">Korte Heuvel 10</div>
  <div class="postcode">5038 CN</div>
  <div class="city">Tilburg</div>
  <div class="price">EUR 375.000 k.k.</div>
  <div class="status">Beschikbaar</div>
  <div class="area">96 m2</div>
  <div class="rooms">4 kamers</div>
  <div class="type">Eengezinswoning</div>
  <div class="broker">Voorbeeld Makelaar</div>
  <div class="evidence">sample-huislijn-card</div>
  <img src="https://images.example/huislijn.jpg">
</article>
"""

PARARIUS_SAMPLE = """
<section class="search-list__item">
  <a class="listing-search-item__link" href="https://www.pararius.nl/huis-te-koop/tilburg/example"></a>
  <div class="listing-search-item__title">Besterdring 12</div>
  <div class="listing-search-item__location">Tilburg</div>
  <div class="listing-search-item__price">EUR 420.000 k.k.</div>
  <div class="listing-search-item__features--area">88 m2</div>
  <div class="listing-search-item__features--rooms">3 kamers</div>
  <div class="listing-search-item__features--property-type">Appartement</div>
  <div class="listing-search-item__brand">Pararius Sample Broker</div>
  <div class="listing-search-item__label">Nieuw</div>
  <div class="source-evidence">sample-pararius-card</div>
  <img src="https://images.example/pararius.jpg">
</section>
"""

FUNDA_SAMPLE = """
<div class="search-result">
  <a class="search-result__header-title-container" href="https://www.funda.nl/detail/koop/tilburg/huis-sample/12345678/"></a>
  <div class="search-result__header-title-col">Goirkestraat 88</div>
  <div class="search-result__header-subtitle-col">Tilburg</div>
  <div class="search-result-price">EUR 399.000 k.k.</div>
  <div class="search-result-kenmerken-woonopp">91 m2</div>
  <div class="search-result-kenmerken-aantalkamers">4 kamers</div>
  <div class="search-result__property-type">Woonhuis</div>
  <div class="search-result-status">Beschikbaar</div>
  <div class="search-result-broker">Funda Benchmark Broker</div>
  <div class="source-evidence">sample-funda-card</div>
  <img src="https://images.example/funda.jpg">
</div>
"""


def _listing(property_url: str, address_raw: str = "", price_raw: str = "") -> PortalListing:
    return PortalListing(
        portal="huislijn",
        portal_mode=PortalMode.PRODUCTION_CANDIDATE_WITH_PERMISSION,
        city_query="Tilburg",
        search_url="https://example.test/search",
        page_number=1,
        property_url=property_url,
        address_raw=address_raw,
        price_raw=price_raw,
    )


def _repeat_cards(sample_html: str, wrapper_start: str = "", wrapper_end: str = "", count: int = 1) -> str:
    return wrapper_start + "\n".join(sample_html.replace("example", f"example-{index}") for index in range(count)) + wrapper_end


def test_source_status_contains_expected_values() -> None:
    assert {status.value for status in SourceStatus} == {
        "success",
        "partial_success",
        "blocked_captcha",
        "http_403",
        "http_429",
        "timeout",
        "requires_js",
        "parser_broken",
        "permission_required",
        "benchmark_only",
        "disabled",
    }


def test_portal_mode_contains_expected_values() -> None:
    assert {mode.value for mode in PortalMode} == {
        "production_candidate_with_permission",
        "benchmark_only_permission_required",
        "fallback",
        "disabled",
    }


def test_detect_blocked_page_detects_captcha_403_429_and_login_wall() -> None:
    assert detect_blocked_page("<html>captcha challenge</html>", 200) == SourceStatus.BLOCKED_CAPTCHA
    assert detect_blocked_page("<html></html>", 403) == SourceStatus.HTTP_403
    assert detect_blocked_page("<html></html>", 429) == SourceStatus.HTTP_429
    assert detect_blocked_page("<html>Please sign in to continue</html>", 200) == SourceStatus.PERMISSION_REQUIRED


def test_fill_rates_work() -> None:
    listings = [
        _listing("https://example.test/1", address_raw="Street 1", price_raw="EUR 300.000"),
        _listing("https://example.test/2", address_raw="", price_raw=""),
    ]
    assert calculate_fill_rate(listings, "address_raw") == 0.5
    assert calculate_fill_rate(listings, "price_raw") == 0.5


def test_duplicate_url_rate_works() -> None:
    listings = [
        _listing("https://example.test/1"),
        _listing("https://example.test/1"),
        _listing("https://example.test/2"),
    ]
    assert calculate_duplicate_url_rate(listings) == 1 / 3


def test_dedup_key_for_listing_works() -> None:
    assert dedup_key_for_listing(_listing("HTTPS://EXAMPLE.TEST/1 ")) == "https://example.test/1"
    no_url_listing = _listing("", address_raw=" Korte Heuvel 10 ", price_raw=" EUR 375.000 ")
    assert dedup_key_for_listing(no_url_listing) == "huislijn|tilburg|korte heuvel 10||eur 375.000"


def test_huislijn_sample_parser_returns_listing() -> None:
    listings = huislijn.parse_listing_cards(HUISLIJN_SAMPLE, "Tilburg", huislijn.build_search_url("Tilburg"), 1)
    assert len(listings) >= 1
    assert listings[0].address_raw == "Korte Heuvel 10"


def test_pararius_sample_parser_returns_listing() -> None:
    listings = pararius.parse_listing_cards(PARARIUS_SAMPLE, "Tilburg", pararius.build_search_url("Tilburg"), 1)
    assert len(listings) >= 1
    assert listings[0].portal_mode == PortalMode.BENCHMARK_ONLY_PERMISSION_REQUIRED


def test_funda_sample_parser_returns_listing_and_is_benchmark_only() -> None:
    listings = funda.parse_listing_cards(FUNDA_SAMPLE, "Tilburg", funda.build_search_url("Tilburg"), 1)
    assert len(listings) >= 1
    assert funda.portal_mode == PortalMode.BENCHMARK_ONLY_PERMISSION_REQUIRED
    assert listings[0].portal_mode == PortalMode.BENCHMARK_ONLY_PERMISSION_REQUIRED


def test_portal_build_search_urls_accept_page_argument() -> None:
    assert huislijn.build_search_url("Tilburg", page=1) == "https://www.huislijn.nl/koopwoning/nederland/tilburg"
    assert pararius.build_search_url("Tilburg", page=1) == "https://www.pararius.nl/koopwoningen/tilburg"
    assert funda.build_search_url("Tilburg", page=1) == (
        "https://www.funda.nl/zoeken/koop?selected_area=%5B%22tilburg%22%5D"
    )


def test_generate_markdown_report_includes_source_status_and_recommended_use(tmp_path: Path) -> None:
    city_result = summarize_city_result(
        portal="funda",
        portal_mode=PortalMode.BENCHMARK_ONLY_PERMISSION_REQUIRED,
        city_query="Tilburg",
        search_url=funda.build_search_url("Tilburg"),
        source_status=SourceStatus.SUCCESS,
        listings=funda.parse_listing_cards(FUNDA_SAMPLE, "Tilburg", funda.build_search_url("Tilburg"), 1),
        notes=["sample-only"],
    )
    result = PortalSpikeResult(city_results=[city_result], generated_at="2026-06-18T19:00:00Z")
    report_text = generate_markdown_report(result)
    assert "source_status: success" in report_text
    assert "recommended_use: benchmark_only" in report_text
    assert "safe_to_compare_removals: true" in report_text

    output_paths = write_csv_outputs(result, tmp_path / "outputs")
    assert output_paths["report_md"].exists()
    assert output_paths["listings_csv"].exists()
    assert output_paths["city_summary_csv"].exists()
    assert output_paths["dedup_summary_csv"].exists()


def test_no_live_network_calls() -> None:
    original_socket = socket.socket

    def _fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access should not be used by sample parsers")

    socket.socket = _fail_socket  # type: ignore[assignment]
    try:
        assert huislijn.parse_listing_cards(HUISLIJN_SAMPLE, "Tilburg", huislijn.build_search_url("Tilburg"), 1)
        assert pararius.parse_listing_cards(PARARIUS_SAMPLE, "Tilburg", pararius.build_search_url("Tilburg"), 1)
        assert funda.parse_listing_cards(FUNDA_SAMPLE, "Tilburg", funda.build_search_url("Tilburg"), 1)
    finally:
        socket.socket = original_socket  # type: ignore[assignment]


def test_live_flag_is_disabled_by_default_and_sample_mode_does_not_fetch(monkeypatch, tmp_path: Path) -> None:
    sample_path = tmp_path / "huislijn_sample.html"
    sample_path.write_text(HUISLIJN_SAMPLE, encoding="utf-8")

    def _fail_fetch(*args, **kwargs):
        raise AssertionError("sample mode must not perform live fetches")

    monkeypatch.setattr(RUNNER, "fetch_url", _fail_fetch)
    args = RUNNER.parse_args(
        [
            "--portal",
            "huislijn",
            "--city",
            "Tilburg",
            "--sample-html",
            str(sample_path),
            "--output-dir",
            str(tmp_path / "outputs"),
        ]
    )
    assert args.live is False
    result, output_paths = RUNNER.run_sample_mode(args, "20260618T190000Z")
    assert len(result.city_results) == 1
    assert result.city_results[0].source_status == SourceStatus.SUCCESS
    assert output_paths["report_md"].exists()


def test_cli_runs_sample_only_with_local_html(tmp_path: Path) -> None:
    sample_path = tmp_path / "huislijn_sample.html"
    sample_path.write_text(HUISLIJN_SAMPLE, encoding="utf-8")
    output_dir = tmp_path / "portal_spike"
    command = [
        sys.executable,
        "scripts/run_portal_inventory_spike.py",
        "--portal",
        "huislijn",
        "--city",
        "Tilburg",
        "--sample-html",
        str(sample_path),
        "--output-dir",
        str(output_dir),
    ]
    completed = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=True)
    assert "portal_inventory_report.md" in completed.stdout
    assert (output_dir / "portal_inventory_report.md").exists()
    assert (output_dir / "portal_inventory_sample.csv").exists()
    assert (output_dir / "portal_city_summary.csv").exists()
    assert (output_dir / "portal_dedup_summary.csv").exists()


def test_live_run_continues_if_one_source_fails(monkeypatch, tmp_path: Path) -> None:
    def _fake_fetch(url: str, timeout_seconds: int = 20):
        if "huislijn" in url:
            return FetchResult(
                url=url,
                status_code=429,
                html="<html>Too many requests</html>",
                source_status=SourceStatus.HTTP_429,
                error_message="HTTP Error 429",
                elapsed_ms=10,
            )
        return FetchResult(
            url=url,
            status_code=200,
            html=PARARIUS_SAMPLE,
            source_status=SourceStatus.SUCCESS,
            error_message="",
            elapsed_ms=10,
        )

    monkeypatch.setattr(RUNNER, "fetch_url", _fake_fetch)
    monkeypatch.setattr(RUNNER, "polite_sleep", lambda seconds: None)
    args = SimpleNamespace(
        live=True,
        portals=["huislijn", "pararius"],
        cities=["Tilburg"],
        delay_seconds=0.0,
        timeout_seconds=20,
        output_dir=tmp_path / "live_outputs",
    )
    result, output_paths = RUNNER.run_live_mode(args, "20260618T190000Z")
    statuses = {(city.portal, city.city_query): city.source_status for city in result.city_results}
    assert statuses[("huislijn", "Tilburg")] == SourceStatus.HTTP_429
    assert statuses[("pararius", "Tilburg")] == SourceStatus.SUCCESS
    assert output_paths["city_summary_csv"].exists()


def test_live_limits_are_respected_per_portal(monkeypatch) -> None:
    multi_huislijn = _repeat_cards(HUISLIJN_SAMPLE, count=25)
    multi_pararius = _repeat_cards(PARARIUS_SAMPLE, count=25)
    multi_funda = _repeat_cards(FUNDA_SAMPLE, count=25)

    def _fake_fetch(url: str, timeout_seconds: int = 20):
        if "huislijn" in url:
            return FetchResult(url=url, status_code=200, html=multi_huislijn, source_status=SourceStatus.SUCCESS, error_message="", elapsed_ms=10)
        if "pararius" in url:
            return FetchResult(url=url, status_code=200, html=multi_pararius, source_status=SourceStatus.SUCCESS, error_message="", elapsed_ms=10)
        return FetchResult(url=url, status_code=200, html=multi_funda, source_status=SourceStatus.SUCCESS, error_message="", elapsed_ms=10)

    monkeypatch.setattr(RUNNER, "fetch_url", _fake_fetch)
    monkeypatch.setattr(RUNNER, "polite_sleep", lambda seconds: None)

    huislijn_result = RUNNER.run_live_city(RUNNER.LivePortalRunContext("huislijn", "Tilburg", 0.0, 20))
    pararius_result = RUNNER.run_live_city(RUNNER.LivePortalRunContext("pararius", "Tilburg", 0.0, 20))
    funda_result = RUNNER.run_live_city(RUNNER.LivePortalRunContext("funda", "Tilburg", 0.0, 20))

    assert len(huislijn_result.listings) == 30
    assert huislijn_result.page_number == 2
    assert len(pararius_result.listings) == 20
    assert len(funda_result.listings) == 15


def test_safe_to_compare_removals_false_if_status_not_success(tmp_path: Path) -> None:
    city_result = summarize_city_result(
        portal="pararius",
        portal_mode=PortalMode.BENCHMARK_ONLY_PERMISSION_REQUIRED,
        city_query="Tilburg",
        search_url=pararius.build_search_url("Tilburg"),
        source_status=SourceStatus.PERMISSION_REQUIRED,
        listings=[],
        blocked_reason="permission_required",
    )
    result = PortalSpikeResult(city_results=[city_result], generated_at="20260618T190000Z")
    output_dir = tmp_path / "outputs"
    write_csv_outputs(result, output_dir)

    rows = list(csv.DictReader((output_dir / "portal_city_summary.csv").open(encoding="utf-8")))
    assert rows[0]["safe_to_compare_removals"] == "false"
    report_text = (output_dir / "portal_inventory_report.md").read_text(encoding="utf-8")
    assert "safe_to_compare_removals: false" in report_text


def test_live_outputs_are_written_to_tmp_without_real_internet(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    def _fake_fetch(url: str, timeout_seconds: int = 20):
        calls.append(url)
        return FetchResult(
            url=url,
            status_code=200,
            html=HUISLIJN_SAMPLE,
            source_status=SourceStatus.SUCCESS,
            error_message="",
            elapsed_ms=10,
        )

    monkeypatch.setattr(RUNNER, "fetch_url", _fake_fetch)
    monkeypatch.setattr(RUNNER, "polite_sleep", lambda seconds: None)

    args = SimpleNamespace(
        live=True,
        portals=["huislijn"],
        cities=["Tilburg"],
        delay_seconds=0.0,
        timeout_seconds=20,
        output_dir=tmp_path / "artifact_root",
    )
    result, output_paths = RUNNER.run_live_mode(args, "20260618T190000Z")
    assert calls
    assert result.city_results[0].source_status == SourceStatus.SUCCESS
    assert output_paths["report_md"].parent == tmp_path / "artifact_root"
    assert output_paths["report_md"].exists()
    assert output_paths["listings_csv"].exists()
    assert output_paths["city_summary_csv"].exists()
    assert output_paths["dedup_summary_csv"].exists()
