from __future__ import annotations

import time
from contextlib import AbstractContextManager

from playwright.sync_api import Error, TimeoutError, sync_playwright

from .models import CrawlResult, PropertySource


def _warn(message: str) -> None:
    print(f"[property-discovery] warning {message}", flush=True)


class ListingPageCrawler(AbstractContextManager["ListingPageCrawler"]):
    def __init__(self, timeout_ms: int = 30000) -> None:
        self.timeout_ms = timeout_ms
        self._playwright = None
        self._browser = None

    def __enter__(self) -> "ListingPageCrawler":
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
        return None

    def _safe_cleanup(self, label: str, action) -> None:
        try:
            action()
        except BaseException as exc:  # pragma: no cover - defensive cleanup path
            _warn(f"{label} failed during cleanup: {exc}")

    def close(self) -> None:
        browser = self._browser
        playwright = self._playwright
        self._browser = None
        self._playwright = None

        if browser is not None:
            self._safe_cleanup("browser.close", browser.close)
        if playwright is not None:
            self._safe_cleanup("playwright.stop", playwright.stop)

    def crawl(self, source: PropertySource) -> CrawlResult:
        return self.fetch(source.aanbod_url, source)

    def fetch(self, url: str, source: PropertySource, timeout_ms: int | None = None) -> CrawlResult:
        if self._browser is None:
            raise RuntimeError("ListingPageCrawler must be opened before crawling")

        started = time.perf_counter()
        page = self._browser.new_page()
        effective_timeout_ms = timeout_ms if timeout_ms is not None else self.timeout_ms
        page.set_default_timeout(effective_timeout_ms)
        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=effective_timeout_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=min(effective_timeout_ms, 5000))
            except TimeoutError:
                pass
            final_url = page.url or url or source.aanbod_url
            html = page.content()
            if not html.strip():
                raise RuntimeError("empty page content")
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            return CrawlResult(
                source=source,
                ok=True,
                final_url=final_url,
                html=html,
                error="" if response is not None else "missing response object",
                elapsed_ms=elapsed_ms,
            )
        except (TimeoutError, Error, RuntimeError) as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            return CrawlResult(
                source=source,
                ok=False,
                final_url=url or source.aanbod_url,
                error=str(exc),
                elapsed_ms=elapsed_ms,
                timed_out=isinstance(exc, TimeoutError),
            )
        finally:
            self._safe_cleanup("page.close", page.close)
