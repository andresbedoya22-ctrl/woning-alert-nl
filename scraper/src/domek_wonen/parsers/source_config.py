from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .models import ParserInput


_UNRESERVED_QUERY_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"


class SourceConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PaginatedAPIConfig:
    api_base_url: str
    method: str = "GET"
    page_param: str = "page"
    limit_param: str = "limit"
    start_page: int = 1
    limit: int = 24
    max_pages: int = 2
    items_path: str = "docs"
    total_count_path: str = "totalDocs"
    total_pages_path: str = "totalPages"
    has_next_path: str = "hasNextPage"
    next_page_path: str = "nextPage"
    static_query_params: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ParserSourceConfig:
    source_id: str
    source_domain: str
    listing_url: str
    parser_family: str
    delivery_mode: str
    api: PaginatedAPIConfig | None = None
    notes: str = ""


def load_parser_source_config(path: Path) -> ParserSourceConfig:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SourceConfigError(f"invalid_source_config_json:{path}") from exc

    if not isinstance(payload, dict):
        raise SourceConfigError("source_config_must_be_object")

    api_payload = payload.get("api")
    api = _load_api_config(api_payload) if api_payload is not None else None

    config = ParserSourceConfig(
        source_id=_required_text(payload, "source_id"),
        source_domain=_required_text(payload, "source_domain"),
        listing_url=_required_text(payload, "listing_url"),
        parser_family=_required_text(payload, "parser_family"),
        delivery_mode=_required_text(payload, "delivery_mode"),
        api=api,
        notes=_optional_text(payload, "notes"),
    )
    _validate_source_config(config)
    return config


def build_paginated_api_url(config: ParserSourceConfig, page: int) -> str:
    api = config.api
    if api is None:
        raise SourceConfigError("missing_paginated_api_config")
    if page < api.start_page:
        raise SourceConfigError("page_before_start_page")
    if page > api.max_pages:
        raise SourceConfigError("page_after_max_pages")

    query_params = {
        **api.static_query_params,
        api.page_param: str(page),
        api.limit_param: str(api.limit),
    }
    query_string = "&".join(
        f"{_quote_query_component(key)}={_quote_query_component(value)}" for key, value in query_params.items()
    )
    separator = "&" if "?" in api.api_base_url else "?"
    return f"{api.api_base_url}{separator}{query_string}" if query_string else api.api_base_url


def build_parser_input_from_api_json(
    config: ParserSourceConfig,
    json_content: str,
    *,
    page: int,
) -> ParserInput:
    api = config.api
    if api is None:
        raise SourceConfigError("missing_paginated_api_config")

    return ParserInput(
        source_id=config.source_id,
        source_domain=config.source_domain,
        source_url=build_paginated_api_url(config, page),
        content=json_content,
        content_type="json",
        metadata={
            "parser_family": config.parser_family,
            "page": str(page),
            "limit": str(api.limit),
            "listing_url": config.listing_url,
        },
    )


def _load_api_config(payload: Any) -> PaginatedAPIConfig:
    if not isinstance(payload, dict):
        raise SourceConfigError("api_config_must_be_object")

    static_query_params = payload.get("static_query_params", {})
    if not isinstance(static_query_params, dict):
        raise SourceConfigError("static_query_params_must_be_object")

    return PaginatedAPIConfig(
        api_base_url=_required_text(payload, "api_base_url"),
        method=_optional_text(payload, "method", default="GET"),
        page_param=_optional_text(payload, "page_param", default="page"),
        limit_param=_optional_text(payload, "limit_param", default="limit"),
        start_page=_optional_int(payload, "start_page", default=1),
        limit=_optional_int(payload, "limit", default=24),
        max_pages=_optional_int(payload, "max_pages", default=2),
        items_path=_optional_text(payload, "items_path", default="docs"),
        total_count_path=_optional_text(payload, "total_count_path", default="totalDocs"),
        total_pages_path=_optional_text(payload, "total_pages_path", default="totalPages"),
        has_next_path=_optional_text(payload, "has_next_path", default="hasNextPage"),
        next_page_path=_optional_text(payload, "next_page_path", default="nextPage"),
        static_query_params={str(key): str(value) for key, value in static_query_params.items()},
    )


def _validate_source_config(config: ParserSourceConfig) -> None:
    if "." not in config.source_domain:
        raise SourceConfigError("invalid_source_domain")
    if not config.listing_url.startswith(("http://", "https://")):
        raise SourceConfigError("invalid_listing_url")
    if not config.parser_family:
        raise SourceConfigError("missing_parser_family")
    if not config.delivery_mode:
        raise SourceConfigError("missing_delivery_mode")
    if config.api is not None and not config.api.api_base_url.startswith(("http://", "https://")):
        raise SourceConfigError("invalid_api_base_url")


def _required_text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SourceConfigError(f"missing_{key}")
    return value.strip()


def _optional_text(payload: Mapping[str, Any], key: str, *, default: str = "") -> str:
    value = payload.get(key, default)
    if value is None:
        return default
    if not isinstance(value, str):
        raise SourceConfigError(f"invalid_{key}")
    return value.strip()


def _optional_int(payload: Mapping[str, Any], key: str, *, default: int) -> int:
    value = payload.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise SourceConfigError(f"invalid_{key}")
    return value


def _quote_query_component(value: str) -> str:
    encoded: list[str] = []
    for byte in str(value).encode("utf-8"):
        char = chr(byte)
        if char in _UNRESERVED_QUERY_CHARS:
            encoded.append(char)
        else:
            encoded.append(f"%{byte:02X}")
    return "".join(encoded)
