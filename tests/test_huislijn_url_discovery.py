from __future__ import annotations

import csv
import importlib.util
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.portals.live_fetch import FetchResult
from domek_wonen.portals.models import SourceStatus
from domek_wonen.portals.huislijn_url_discovery import (
    build_candidate_probes,
    detect_embedded_state,
    detect_json_ld,
    detect_listing_like_links,
    detect_search_form,
    run_huislijn_url_discovery,
    summarize_probe,
    write_outputs,
)


def _load_runner_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_huislijn_url_discovery.py"
    spec = importlib.util.spec_from_file_location("run_huislijn_url_discovery", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RUNNER = _load_runner_module()


def test_410_is_recorded_as_wrong_url_410_with_evidence() -> None:
    probe = build_candidate_probes(["Tilburg"])[1]
    fetch_result = FetchResult(
        url=probe.url,
        status_code=410,
        html="<html><body>Gone</body></html>",
        source_status=SourceStatus.PARSER_BROKEN,
        error_message="HTTP Error 410: Gone",
        elapsed_ms=25,
    )
    probe_result = summarize_probe(probe, fetch_result)
    assert probe_result.recommendation == "wrong_url_410"
    assert "410" in probe_result.evidence_snippet or "Gone" in probe_result.evidence_snippet


def test_listing_like_links_are_detected() -> None:
    html = """
    <html><body>
      <article class="listing-card" data-url="https://www.huislijn.nl/koopwoning/nederland/tilburg/123/sample"></article>
      <a href="/koopwoning/nederland/tilburg/123/sample">Bekijk</a>
    </body></html>
    """
    assert detect_listing_like_links(html) is True


def test_json_ld_is_detected() -> None:
    html = '<script type="application/ld+json">{"@context":"https://schema.org"}</script>'
    assert detect_json_ld(html) is True


def test_embedded_state_is_detected() -> None:
    html = '<script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{}}}</script>'
    assert detect_embedded_state(html) is True


def test_search_form_is_detected() -> None:
    html = '<html><form action="/zoeken"><input name="plaats"><button>Zoek</button></form></html>'
    assert detect_search_form(html) is True


def test_request_limit_is_respected(monkeypatch) -> None:
    calls: list[str] = []

    def _fake_fetch(url: str, timeout_seconds: int = 20):
        calls.append(url)
        return FetchResult(
            url=url,
            status_code=200,
            html="<html><body>zoek koopwoning</body></html>",
            source_status=SourceStatus.SUCCESS,
            error_message="",
            elapsed_ms=5,
        )

    monkeypatch.setattr("domek_wonen.portals.huislijn_url_discovery.fetch_url", _fake_fetch)
    monkeypatch.setattr("domek_wonen.portals.huislijn_url_discovery.polite_sleep", lambda seconds: None)
    result = run_huislijn_url_discovery(["Tilburg", "Utrecht"], delay_seconds=0.0, timeout_seconds=20, max_requests=3)
    assert result.requests_used == 3
    assert len(result.probe_results) == 3
    assert len(calls) == 3
    assert result.stopped_early is True
    assert result.stop_reason == "max_requests_reached=3"


def test_stop_on_403_429_captcha_or_login_wall(monkeypatch) -> None:
    responses = [
        FetchResult(
            url="https://www.huislijn.nl/",
            status_code=200,
            html="<html><body>zoek</body></html>",
            source_status=SourceStatus.SUCCESS,
            error_message="",
            elapsed_ms=5,
        ),
        FetchResult(
            url="https://www.huislijn.nl/koopwoningen/tilburg",
            status_code=403,
            html="<html><body>forbidden</body></html>",
            source_status=SourceStatus.HTTP_403,
            error_message="HTTP Error 403: Forbidden",
            elapsed_ms=5,
        ),
        FetchResult(
            url="https://www.huislijn.nl/koopwoningen/utrecht",
            status_code=200,
            html="<html><body>should not be fetched</body></html>",
            source_status=SourceStatus.SUCCESS,
            error_message="",
            elapsed_ms=5,
        ),
    ]

    def _fake_fetch(url: str, timeout_seconds: int = 20):
        return responses.pop(0)

    monkeypatch.setattr("domek_wonen.portals.huislijn_url_discovery.fetch_url", _fake_fetch)
    monkeypatch.setattr("domek_wonen.portals.huislijn_url_discovery.polite_sleep", lambda seconds: None)
    result = run_huislijn_url_discovery(["Tilburg", "Utrecht"], delay_seconds=0.0, timeout_seconds=20, max_requests=10)
    assert result.requests_used == 2
    assert result.stopped_early is True
    assert result.stop_reason == "stop_source_status=http_403"


def test_write_outputs_writes_tmp_files(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "domek_wonen.portals.huislijn_url_discovery.fetch_url",
        lambda url, timeout_seconds=20: FetchResult(
            url=url,
            status_code=200,
            html='<html><body><script type="application/ld+json">{}</script></body></html>',
            source_status=SourceStatus.SUCCESS,
            error_message="",
            elapsed_ms=5,
        ),
    )
    monkeypatch.setattr("domek_wonen.portals.huislijn_url_discovery.polite_sleep", lambda seconds: None)
    result = run_huislijn_url_discovery(["Tilburg"], delay_seconds=0.0, timeout_seconds=20, max_requests=10)
    output_paths = write_outputs(result, tmp_path / "huislijn")
    assert output_paths["report_md"].exists()
    assert output_paths["candidates_csv"].exists()
    rows = list(csv.DictReader(output_paths["candidates_csv"].open(encoding="utf-8")))
    assert rows


def test_cli_rejects_request_budget_above_ten() -> None:
    try:
        RUNNER.parse_args(["--cities", "Tilburg", "--max-requests", "11"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("parse_args should reject max-requests > 10")
