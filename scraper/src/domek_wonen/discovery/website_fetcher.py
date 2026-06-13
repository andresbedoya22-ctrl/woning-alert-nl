from __future__ import annotations

import time
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Iterable
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

import httpx

from .config import LIVE_AANBOD_DELAY_SECONDS, LIVE_AANBOD_TIMEOUT_SECONDS, LIVE_AANBOD_USER_AGENT


@dataclass(slots=True)
class FetchResponse:
    url: str
    status_code: int = 0
    text: str = ""
    content_type: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.status_code == 200 and bool(self.text.strip())


class _LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value:
                self.links.append(value)


class WebsiteFetcher:
    def __init__(
        self,
        *,
        timeout_seconds: float = LIVE_AANBOD_TIMEOUT_SECONDS,
        delay_seconds: float = LIVE_AANBOD_DELAY_SECONDS,
        user_agent: str = LIVE_AANBOD_USER_AGENT,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.delay_seconds = delay_seconds
        self._client = httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": user_agent},
        )

    def close(self) -> None:
        self._client.close()

    def fetch(self, url: str) -> FetchResponse:
        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)
        try:
            response = self._client.get(url)
            content_type = response.headers.get("content-type", "")
            return FetchResponse(
                url=str(response.url).rstrip("/"),
                status_code=response.status_code,
                text=response.text or "",
                content_type=content_type,
            )
        except httpx.HTTPError as exc:
            return FetchResponse(url=url.rstrip("/"), error=str(exc))

    def extract_internal_links(self, base_url: str, html: str) -> list[str]:
        parser = _LinkExtractor()
        try:
            parser.feed(html)
        except Exception:
            return []

        base = urlsplit(base_url)
        seen: set[str] = set()
        results: list[str] = []
        for raw_link in parser.links:
            absolute = urljoin(f"{base_url.rstrip('/')}/", raw_link.strip())
            parsed = urlsplit(absolute)
            if parsed.scheme not in {"http", "https"}:
                continue
            if parsed.netloc.lower() != base.netloc.lower():
                continue
            normalized = absolute.split("#", 1)[0].rstrip("/")
            if normalized in seen:
                continue
            seen.add(normalized)
            results.append(normalized)
        return results

    def parse_sitemap_urls(self, xml_text: str, *, limit: int) -> list[str]:
        if not xml_text.strip():
            return []
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError:
            return []

        urls: list[str] = []
        for element in root.iter():
            tag = element.tag.lower()
            if tag.endswith("loc") and element.text:
                value = element.text.strip().rstrip("/")
                if value:
                    urls.append(value)
                if len(urls) >= limit:
                    break
        return urls


def dedupe_urls(urls: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for url in urls:
        normalized = url.rstrip("/")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered
