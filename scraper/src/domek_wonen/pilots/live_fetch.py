from __future__ import annotations

from collections.abc import Iterable
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .realworks_capture_pilot import CapturePilotResult, CapturePilotSource, run_realworks_capture_pilot


DEFAULT_USER_AGENT = "WoningAlertNL-ControlledPilot/0.1 (+manual advisor review; no bypass)"


class ControlledFetchError(RuntimeError):
    pass


class ControlledFetchStatusError(ControlledFetchError):
    pass


class ControlledFetchContentTypeError(ControlledFetchError):
    pass


def controlled_http_fetch_html(
    url: str,
    *,
    timeout_seconds: float = 10.0,
    user_agent: str = DEFAULT_USER_AGENT,
) -> str:
    request = Request(url, headers={"User-Agent": user_agent})

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            status = getattr(response, "status", None)
            if status is not None and int(status) >= 400:
                raise ControlledFetchStatusError(f"HTTP status {status} for {url}")

            content_type = _response_content_type(response)
            if not _is_html_or_text_content_type(content_type):
                raise ControlledFetchContentTypeError(f"Unsupported content-type {content_type or 'unknown'} for {url}")

            payload = response.read()
            charset = _response_charset(response) or "utf-8"
    except HTTPError as exc:
        raise ControlledFetchStatusError(f"HTTP status {exc.code} for {url}") from exc

    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def run_selected_realworks_live_pilot(
    sources: Iterable[CapturePilotSource],
    *,
    captured_at: str,
    max_sources: int = 3,
) -> list[CapturePilotResult]:
    return run_realworks_capture_pilot(
        sources=sources,
        fetch_html=controlled_http_fetch_html,
        captured_at=captured_at,
        max_sources=max_sources,
    )


def keep_first_source_per_domain(
    sources: Iterable[CapturePilotSource],
    max_sources: int = 3,
) -> tuple[CapturePilotSource, ...]:
    if max_sources <= 0:
        return ()

    selected: list[CapturePilotSource] = []
    seen_domains: set[str] = set()
    for source in sources:
        domain = source.source_domain.strip().lower()
        if not domain or domain in seen_domains:
            continue
        seen_domains.add(domain)
        selected.append(source)
        if len(selected) >= max_sources:
            break
    return tuple(selected)


def _response_content_type(response: object) -> str:
    if hasattr(response, "getheader"):
        value = response.getheader("Content-Type")
        if value:
            return str(value)

    headers = getattr(response, "headers", None)
    if headers is not None and hasattr(headers, "get"):
        value = headers.get("Content-Type")
        if value:
            return str(value)

    return ""


def _response_charset(response: object) -> str:
    headers = getattr(response, "headers", None)
    if headers is not None and hasattr(headers, "get_content_charset"):
        charset = headers.get_content_charset()
        if charset:
            return str(charset)

    content_type = _response_content_type(response)
    for part in content_type.split(";")[1:]:
        key, separator, value = part.strip().partition("=")
        if separator and key.lower() == "charset":
            return value.strip().strip('"')
    return ""


def _is_html_or_text_content_type(content_type: str) -> bool:
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type.startswith("text/") or media_type in {"application/xhtml+xml"} or media_type.endswith("+html")
