from __future__ import annotations

from dataclasses import dataclass
import socket
import time
from urllib import error, request

from domek_wonen.portals.models import SourceStatus
from domek_wonen.portals.portal_inventory_spike import detect_blocked_page, normalize_text

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


@dataclass(slots=True)
class FetchResult:
    url: str
    status_code: int | None
    html: str
    source_status: SourceStatus
    error_message: str
    elapsed_ms: int


def classify_http_status(status_code: int | None, html: str) -> SourceStatus:
    blocked_status = detect_blocked_page(html, status_code)
    if blocked_status is not None:
        return blocked_status

    normalized_html = normalize_text(html)
    normalized_lower = normalized_html.lower()
    if status_code == 200:
        if "<html" in html.lower() and len(normalized_html) >= 80:
            return SourceStatus.SUCCESS
        if any(marker in normalized_lower for marker in ("javascript", "__next", "__nuxt", "root")):
            return SourceStatus.REQUIRES_JS
        return SourceStatus.PARSER_BROKEN

    if status_code is None:
        return SourceStatus.PARSER_BROKEN

    return SourceStatus.PARSER_BROKEN


def map_request_error(exc: BaseException) -> tuple[SourceStatus, str]:
    if isinstance(exc, TimeoutError | socket.timeout):
        return SourceStatus.TIMEOUT, str(exc) or "request timed out"
    if isinstance(exc, error.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, TimeoutError | socket.timeout):
            return SourceStatus.TIMEOUT, str(reason) or "request timed out"
        return SourceStatus.PARSER_BROKEN, str(reason or exc)
    return SourceStatus.PARSER_BROKEN, str(exc) or exc.__class__.__name__


def polite_sleep(seconds: float) -> None:
    time.sleep(max(0.0, seconds))


def fetch_url(url: str, timeout_seconds: int = 20, user_agent: str = DEFAULT_USER_AGENT) -> FetchResult:
    started_at = time.perf_counter()
    request_obj = request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        method="GET",
    )

    try:
        with request.urlopen(request_obj, timeout=timeout_seconds) as response:
            status_code = getattr(response, "status", None)
            charset = response.headers.get_content_charset() or "utf-8"
            html = response.read().decode(charset, errors="replace")
            source_status = classify_http_status(status_code, html)
            return FetchResult(
                url=url,
                status_code=status_code,
                html=html,
                source_status=source_status,
                error_message="",
                elapsed_ms=int((time.perf_counter() - started_at) * 1000),
            )
    except error.HTTPError as exc:
        try:
            charset = exc.headers.get_content_charset() if exc.headers is not None else None
            html = exc.read().decode(charset or "utf-8", errors="replace")
        except Exception:
            html = ""
        source_status = classify_http_status(exc.code, html)
        return FetchResult(
            url=url,
            status_code=exc.code,
            html=html,
            source_status=source_status,
            error_message=str(exc),
            elapsed_ms=int((time.perf_counter() - started_at) * 1000),
        )
    except Exception as exc:
        source_status, error_message = map_request_error(exc)
        return FetchResult(
            url=url,
            status_code=None,
            html="",
            source_status=source_status,
            error_message=error_message,
            elapsed_ms=int((time.perf_counter() - started_at) * 1000),
        )
