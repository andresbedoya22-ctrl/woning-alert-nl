from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit

import httpx

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.discovery.platform_fingerprint import WORDPRESS_SIGNALS

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:  # pragma: no cover
    PlaywrightError = RuntimeError
    PlaywrightTimeoutError = TimeoutError
    sync_playwright = None


DEFAULT_OUTPUT_BASE_DIR = BASE_DIR / "data" / "source_debug" / "kin"
DEFAULT_VARIANTS = [
    "http://www.kinmakelaars.nl/aanbod/wonen/te-koop",
    "https://www.kinmakelaars.nl/aanbod/wonen/te-koop",
    "https://www.kinmakelaars.nl/aanbod/wonen/te-koop?page=1",
]
REALWORKS_SIGNALS = ["realworks", "realworks.nl", "rw-og", "/woningaanbod/", "woningaanbod"]
OGONLINE_SIGNALS = ["website door ogonline", "ogonline", "/aanbod/wonen/te-koop"]
DETAIL_LINK_HINTS = ("/aanbod/wonen/", "/woning/", "/object/", "/aanbod/", "/te-koop/")
PAGINATION_HINTS = ("page=", "?page=", "&page=", "volgende", "next", "pagination")


@dataclass(slots=True)
class DebugObservation:
    mode: str
    requested_url: str
    final_url: str
    http_status: str
    redirect_chain: str
    fetch_duration_seconds: float
    html_length: int
    title: str
    has_trouwlaan_285: bool
    has_roemerhof_16: bool
    has_results_count_hint: bool
    detail_links_count: int
    pagination_links_count: int
    realworks_detected: bool
    realworks_reasons: list[str]
    ogonline_detected: bool
    ogonline_reasons: list[str]
    requires_playwright_inference: str
    error: str = ""
    html: str = ""


class _LinkAndTitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.links: list[str] = []
        self._capture_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self._capture_title = True
        if tag.lower() != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value:
                self.links.append(value.strip())
                return

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._capture_title = False

    def handle_data(self, data: str) -> None:
        if self._capture_title and not self.title:
            normalized = " ".join(data.split())
            if normalized:
                self.title = normalized


def normalize_kin_url_to_https(url: str) -> str:
    parsed = urlsplit((url or "").strip())
    if parsed.scheme.lower() == "http" and parsed.netloc.lower() == "www.kinmakelaars.nl":
        return url.replace("http://www.kinmakelaars.nl", "https://www.kinmakelaars.nl", 1)
    return url


def analyze_html(html: str) -> dict[str, object]:
    parser = _LinkAndTitleParser()
    try:
        parser.feed(html or "")
    except Exception:
        pass
    text = " ".join((html or "").split())
    text_lower = text.lower()
    detail_links_count = sum(1 for href in parser.links if any(hint in href.lower() for hint in DETAIL_LINK_HINTS))
    pagination_links_count = sum(1 for href in parser.links if any(hint in href.lower() for hint in PAGINATION_HINTS))
    return {
        "title": parser.title,
        "has_trouwlaan_285": "trouwlaan 285" in text_lower,
        "has_roemerhof_16": "roemerhof 16" in text_lower,
        "has_results_count_hint": bool(re.search(r"\b\d+\s+resultaten\b", text_lower)),
        "detail_links_count": detail_links_count,
        "pagination_links_count": pagination_links_count,
    }


def detect_signal_reasons(html: str, url: str, signals: list[str], prefix: str) -> tuple[bool, list[str]]:
    haystack = " \n ".join([html or "", url or ""]).lower()
    reasons = [f"signal:{prefix}:{signal}" for signal in signals if signal in haystack]
    return bool(reasons), reasons[:6]


def infer_requires_playwright(*, httpx_observation: DebugObservation | None, playwright_observation: DebugObservation | None) -> str:
    if playwright_observation and playwright_observation.html_length > 0 and (
        httpx_observation is None or playwright_observation.html_length > httpx_observation.html_length * 2
    ):
        return "playwright_recommended"
    if httpx_observation and httpx_observation.html_length > 0 and not httpx_observation.error:
        return "httpx_sufficient"
    if playwright_observation and playwright_observation.html_length > 0:
        return "playwright_recommended"
    return "inconclusive"


def debug_with_httpx(url: str, *, timeout_seconds: float) -> DebugObservation:
    started = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            response = client.get(url)
        duration = time.perf_counter() - started
        html = response.text or ""
        html_analysis = analyze_html(html)
        realworks_detected, realworks_reasons = detect_signal_reasons(html, str(response.url), REALWORKS_SIGNALS, "realworks")
        ogonline_detected, ogonline_reasons = detect_signal_reasons(html, str(response.url), OGONLINE_SIGNALS, "ogonline")
        redirect_chain = " -> ".join(str(item.url) for item in response.history + [response])
        return DebugObservation(
            mode="httpx",
            requested_url=url,
            final_url=str(response.url),
            http_status=str(response.status_code),
            redirect_chain=redirect_chain,
            fetch_duration_seconds=duration,
            html_length=len(html),
            title=str(html_analysis["title"]),
            has_trouwlaan_285=bool(html_analysis["has_trouwlaan_285"]),
            has_roemerhof_16=bool(html_analysis["has_roemerhof_16"]),
            has_results_count_hint=bool(html_analysis["has_results_count_hint"]),
            detail_links_count=int(html_analysis["detail_links_count"]),
            pagination_links_count=int(html_analysis["pagination_links_count"]),
            realworks_detected=realworks_detected,
            realworks_reasons=realworks_reasons,
            ogonline_detected=ogonline_detected,
            ogonline_reasons=ogonline_reasons,
            requires_playwright_inference="pending_comparison",
            html=html,
        )
    except httpx.HTTPError as exc:
        duration = time.perf_counter() - started
        return DebugObservation(
            mode="httpx",
            requested_url=url,
            final_url="",
            http_status="",
            redirect_chain="",
            fetch_duration_seconds=duration,
            html_length=0,
            title="",
            has_trouwlaan_285=False,
            has_roemerhof_16=False,
            has_results_count_hint=False,
            detail_links_count=0,
            pagination_links_count=0,
            realworks_detected=False,
            realworks_reasons=[],
            ogonline_detected=False,
            ogonline_reasons=[],
            requires_playwright_inference="pending_comparison",
            error=str(exc),
        )


def debug_with_playwright(url: str, *, timeout_seconds: float) -> DebugObservation:
    started = time.perf_counter()
    if sync_playwright is None:
        duration = time.perf_counter() - started
        return DebugObservation(
            mode="playwright",
            requested_url=url,
            final_url="",
            http_status="",
            redirect_chain="",
            fetch_duration_seconds=duration,
            html_length=0,
            title="",
            has_trouwlaan_285=False,
            has_roemerhof_16=False,
            has_results_count_hint=False,
            detail_links_count=0,
            pagination_links_count=0,
            realworks_detected=False,
            realworks_reasons=[],
            ogonline_detected=False,
            ogonline_reasons=[],
            requires_playwright_inference="playwright_unavailable",
            error="playwright is not installed",
        )

    responses: list[tuple[str, int]] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_default_timeout(int(timeout_seconds * 1000))

            def _capture_response(response) -> None:
                try:
                    if response.request.resource_type == "document":
                        responses.append((response.url, response.status))
                except Exception:
                    return None
                return None

            page.on("response", _capture_response)
            response = page.goto(url, wait_until="domcontentloaded", timeout=int(timeout_seconds * 1000))
            try:
                page.wait_for_load_state("networkidle", timeout=min(int(timeout_seconds * 1000), 5000))
            except PlaywrightTimeoutError:
                pass
            html = page.content() or ""
            duration = time.perf_counter() - started
            final_url = page.url or url
            html_analysis = analyze_html(html)
            realworks_detected, realworks_reasons = detect_signal_reasons(html, final_url, REALWORKS_SIGNALS, "realworks")
            ogonline_detected, ogonline_reasons = detect_signal_reasons(html, final_url, OGONLINE_SIGNALS, "ogonline")
            status = str(response.status) if response is not None else ""
            redirect_chain = " -> ".join(url for url, _status in responses) if responses else final_url
            page.close()
            browser.close()
            return DebugObservation(
                mode="playwright",
                requested_url=url,
                final_url=final_url,
                http_status=status,
                redirect_chain=redirect_chain,
                fetch_duration_seconds=duration,
                html_length=len(html),
                title=str(html_analysis["title"]),
                has_trouwlaan_285=bool(html_analysis["has_trouwlaan_285"]),
                has_roemerhof_16=bool(html_analysis["has_roemerhof_16"]),
                has_results_count_hint=bool(html_analysis["has_results_count_hint"]),
                detail_links_count=int(html_analysis["detail_links_count"]),
                pagination_links_count=int(html_analysis["pagination_links_count"]),
                realworks_detected=realworks_detected,
                realworks_reasons=realworks_reasons,
                ogonline_detected=ogonline_detected,
                ogonline_reasons=ogonline_reasons,
                requires_playwright_inference="pending_comparison",
                html=html,
            )
    except (PlaywrightTimeoutError, PlaywrightError, RuntimeError) as exc:
        duration = time.perf_counter() - started
        return DebugObservation(
            mode="playwright",
            requested_url=url,
            final_url="",
            http_status="",
            redirect_chain="",
            fetch_duration_seconds=duration,
            html_length=0,
            title="",
            has_trouwlaan_285=False,
            has_roemerhof_16=False,
            has_results_count_hint=False,
            detail_links_count=0,
            pagination_links_count=0,
            realworks_detected=False,
            realworks_reasons=[],
            ogonline_detected=False,
            ogonline_reasons=[],
            requires_playwright_inference="playwright_failed",
            error=str(exc),
        )


def _observation_to_lines(observation: DebugObservation) -> list[str]:
    return [
        f"- mode: {observation.mode}",
        f"- requested_url: {observation.requested_url}",
        f"- final_url: {observation.final_url or '-'}",
        f"- http_status: {observation.http_status or '-'}",
        f"- redirect_chain: {observation.redirect_chain or '-'}",
        f"- fetch_duration_seconds: {observation.fetch_duration_seconds:.2f}",
        f"- html_length: {observation.html_length}",
        f"- title: {observation.title or '-'}",
        f"- contains Trouwlaan 285: {'yes' if observation.has_trouwlaan_285 else 'no'}",
        f"- contains Roemerhof 16: {'yes' if observation.has_roemerhof_16 else 'no'}",
        f"- contains resultados/resultaten hint: {'yes' if observation.has_results_count_hint else 'no'}",
        f"- detail links count approx: {observation.detail_links_count}",
        f"- pagination links count approx: {observation.pagination_links_count}",
        f"- realworks signals: {'yes' if observation.realworks_detected else 'no'}"
        + (f" ({'; '.join(observation.realworks_reasons)})" if observation.realworks_reasons else ""),
        f"- ogonline signals: {'yes' if observation.ogonline_detected else 'no'}"
        + (f" ({'; '.join(observation.ogonline_reasons)})" if observation.ogonline_reasons else ""),
        f"- requires Playwright or httpx is enough: {observation.requires_playwright_inference}",
        f"- error: {observation.error or '-'}",
    ]


def build_report(
    observations_by_url: dict[str, list[DebugObservation]],
    *,
    run_id: str,
    snapshot_path: Path | None,
) -> str:
    lines = [
        "# KIN Timeout Isolation v1",
        "",
        f"- Run timestamp: {run_id}",
        f"- Snapshot HTML saved: {snapshot_path if snapshot_path else 'no'}",
        "",
    ]
    for url, observations in observations_by_url.items():
        lines.append(f"## Variant: {url}")
        for observation in observations:
            lines.extend(_observation_to_lines(observation))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Debug KIN source behavior via httpx and Playwright.")
    parser.add_argument("--timeout-seconds", type=float, default=60.0, help="Timeout per request/page")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = DEFAULT_OUTPUT_BASE_DIR / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    variants = list(DEFAULT_VARIANTS)
    observations_by_url: dict[str, list[DebugObservation]] = {}
    canonical_urls: list[str] = []

    for url in variants:
        httpx_observation = debug_with_httpx(url, timeout_seconds=args.timeout_seconds)
        playwright_observation = debug_with_playwright(url, timeout_seconds=args.timeout_seconds)
        httpx_observation.requires_playwright_inference = infer_requires_playwright(
            httpx_observation=httpx_observation,
            playwright_observation=playwright_observation,
        )
        playwright_observation.requires_playwright_inference = httpx_observation.requires_playwright_inference
        observations_by_url[url] = [httpx_observation, playwright_observation]
        for final_url in [httpx_observation.final_url, playwright_observation.final_url]:
            normalized = normalize_kin_url_to_https(final_url)
            if normalized and normalized not in variants and normalized not in canonical_urls:
                canonical_urls.append(normalized)

    for url in canonical_urls:
        httpx_observation = debug_with_httpx(url, timeout_seconds=args.timeout_seconds)
        playwright_observation = debug_with_playwright(url, timeout_seconds=args.timeout_seconds)
        httpx_observation.requires_playwright_inference = infer_requires_playwright(
            httpx_observation=httpx_observation,
            playwright_observation=playwright_observation,
        )
        playwright_observation.requires_playwright_inference = httpx_observation.requires_playwright_inference
        observations_by_url[url] = [httpx_observation, playwright_observation]

    best_html_observation = max(
        (item for items in observations_by_url.values() for item in items),
        key=lambda item: item.html_length,
        default=None,
    )
    snapshot_path: Path | None = None
    if best_html_observation and best_html_observation.html:
        snapshot_path = output_dir / "kin_debug_snapshot.html"
        snapshot_path.write_text(best_html_observation.html, encoding="utf-8")

    report_path = output_dir / "kin_debug_report.md"
    report_path.write_text(build_report(observations_by_url, run_id=run_id, snapshot_path=snapshot_path), encoding="utf-8")
    print(run_id, flush=True)
    print(report_path, flush=True)
    if snapshot_path:
        print(snapshot_path, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
