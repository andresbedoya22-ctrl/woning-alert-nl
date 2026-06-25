from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from domek_wonen.parsers.source_config import load_parser_source_config

from .ogonline_xhr_paginated_runner import PaginatedRunResult, run_ogonline_xhr_paginated_config


DEFAULT_JSON_USER_AGENT = "WoningAlertNL-ControlledPilot/0.1 (+manual advisor review; no bypass)"


class ControlledJSONFetchError(RuntimeError):
    pass


class ControlledJSONFetchStatusError(ControlledJSONFetchError):
    pass


class ControlledJSONFetchContentTypeError(ControlledJSONFetchError):
    pass


class ControlledJSONFetchParseError(ControlledJSONFetchError):
    pass


def controlled_http_fetch_json(
    url: str,
    *,
    timeout_seconds: float = 10.0,
    user_agent: str = DEFAULT_JSON_USER_AGENT,
) -> str:
    request = Request(url, headers={"User-Agent": user_agent})

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            status = getattr(response, "status", None)
            if status is not None and int(status) >= 400:
                raise ControlledJSONFetchStatusError(f"HTTP status {status} for {url}")

            content_type = _response_content_type(response)
            payload = response.read()
            charset = _response_charset(response) or "utf-8"
    except HTTPError as exc:
        raise ControlledJSONFetchStatusError(f"HTTP status {exc.code} for {url}") from exc

    if not _is_json_or_text_content_type(content_type):
        raise ControlledJSONFetchContentTypeError(f"Unsupported content-type {content_type or 'unknown'} for {url}")

    try:
        text = payload.decode(charset)
    except LookupError:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ControlledJSONFetchParseError(f"Could not decode JSON payload for {url}") from exc

    try:
        json.loads(text)
    except json.JSONDecodeError as exc:
        raise ControlledJSONFetchParseError(f"Invalid JSON payload for {url}") from exc

    return text


def run_kin_ogonline_live_paginated_pilot(
    *,
    config_path: Path,
    max_pages: int = 2,
) -> PaginatedRunResult:
    config = load_parser_source_config(config_path)
    return run_ogonline_xhr_paginated_config(
        config,
        fetch_json=controlled_http_fetch_json,
        max_pages=max_pages,
    )


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


def _is_json_or_text_content_type(content_type: str) -> bool:
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type in {"application/json", "text/json", "text/plain"} or media_type.endswith("+json")
