"""
Compliance Gate - robots.txt per domain.
RULE: No other module in the V4 pipeline may make network requests
without calling can_fetch(domain, path) first and receiving True.
This is the single network guardian of the pipeline.
"""

from __future__ import annotations

import logging
import socket
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlunsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from domek_wonen.runtime_settings import load_runtime_settings


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _RobotsCacheEntry:
    parser: RobotFileParser | None
    status: str
    crawl_delay: float


_CACHE: dict[str, _RobotsCacheEntry] = {}


def _normalized_domain(domain: str) -> str:
    return domain.strip().lower()


def _default_delay() -> float:
    settings = load_runtime_settings(load_dotenv_file=False)
    return float(
        getattr(
            settings,
            "REQUEST_DELAY_SECONDS",
            getattr(settings, "min_request_interval_seconds", 0),
        )
    )


def _user_agent() -> str:
    settings = load_runtime_settings(load_dotenv_file=False)
    return getattr(settings, "USER_AGENT", settings.user_agent)


def _timeout_seconds() -> float:
    settings = load_runtime_settings(load_dotenv_file=False)
    return float(getattr(settings, "request_timeout_seconds", 20))


def _build_robots_url(domain: str) -> str:
    return urlunsplit(("https", domain, "/robots.txt", "", ""))


def _download_robots_txt(domain: str) -> tuple[int | None, str]:
    request = Request(_build_robots_url(domain), headers={"User-Agent": _user_agent()})
    with urlopen(request, timeout=_timeout_seconds()) as response:
        status_code = getattr(response, "status", None)
        payload = response.read()
    return status_code, payload.decode("utf-8", errors="ignore")


def fetch_robots(domain: str) -> None:
    normalized_domain = _normalized_domain(domain)
    if normalized_domain in _CACHE:
        return

    parser = RobotFileParser()
    default_delay = _default_delay()

    try:
        _status_code, content = _download_robots_txt(normalized_domain)
    except HTTPError as exc:
        if exc.code == 404:
            logger.info("robots.txt unreachable with 404 for domain %s", normalized_domain)
        else:
            logger.warning("robots.txt request failed for domain %s with HTTP %s", normalized_domain, exc.code)
        _CACHE[normalized_domain] = _RobotsCacheEntry(
            parser=None,
            status="robots_unreachable",
            crawl_delay=default_delay,
        )
        return
    except (TimeoutError, socket.timeout, URLError, OSError) as exc:
        logger.warning("robots.txt request failed for domain %s: %s", normalized_domain, exc)
        _CACHE[normalized_domain] = _RobotsCacheEntry(
            parser=None,
            status="robots_unreachable",
            crawl_delay=default_delay,
        )
        return

    try:
        parser.parse(content.splitlines())
        parser_crawl_delay = parser.crawl_delay(_user_agent())
        crawl_delay_value = default_delay if parser_crawl_delay is None else float(parser_crawl_delay)
        root_allowed = parser.can_fetch(_user_agent(), "/")
        status = "allow" if root_allowed else "disallow"
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("robots.txt parse failed for domain %s: %s", normalized_domain, exc)
        _CACHE[normalized_domain] = _RobotsCacheEntry(
            parser=None,
            status="robots_unreachable",
            crawl_delay=default_delay,
        )
        return

    _CACHE[normalized_domain] = _RobotsCacheEntry(
        parser=parser,
        status=status,
        crawl_delay=crawl_delay_value,
    )


def can_fetch(domain: str, path: str = "/") -> bool:
    normalized_domain = _normalized_domain(domain)
    fetch_robots(normalized_domain)
    entry = _CACHE[normalized_domain]

    if entry.status == "robots_unreachable":
        return True
    if entry.status == "disallow":
        return False
    if entry.parser is None:
        return True

    return entry.parser.can_fetch(_user_agent(), path)


def crawl_delay(domain: str) -> float:
    normalized_domain = _normalized_domain(domain)
    fetch_robots(normalized_domain)
    return _CACHE[normalized_domain].crawl_delay


def robots_status(domain: str) -> str:
    normalized_domain = _normalized_domain(domain)
    entry = _CACHE.get(normalized_domain)
    if entry is None:
        return "not_checked"
    return entry.status


def clear_cache() -> None:
    _CACHE.clear()
