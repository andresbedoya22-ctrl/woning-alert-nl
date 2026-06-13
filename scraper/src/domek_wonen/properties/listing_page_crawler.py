from __future__ import annotations

import time
from contextlib import AbstractContextManager

from playwright.sync_api import Error, TimeoutError, sync_playwright

from .models import CrawlResult, PropertySource


class ListingPageCrawler(AbstractContextManager["ListingPageCrawler"]):
    def __init__(self, timeout_ms: int = 15000) -> None:
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

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None

    def crawl(self, source: PropertySource) -> CrawlResult:
        if self._browser is None:
            raise RuntimeError("ListingPageCrawler must be opened before crawling")

        started = time.perf_counter()
        page = self._browser.new_page()
        page.set_default_timeout(self.timeout_ms)
        try:
            response = page.goto(source.aanbod_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=min(self.timeout_ms, 5000))
            except TimeoutError:
                pass
            final_url = page.url or source.aanbod_url
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
            return CrawlResult(source=source, ok=False, final_url=source.aanbod_url, error=str(exc), elapsed_ms=elapsed_ms)
        finally:
            page.close()
