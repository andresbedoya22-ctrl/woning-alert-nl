from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SourceStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    BLOCKED_CAPTCHA = "blocked_captcha"
    HTTP_403 = "http_403"
    HTTP_429 = "http_429"
    TIMEOUT = "timeout"
    REQUIRES_JS = "requires_js"
    PARSER_BROKEN = "parser_broken"
    PERMISSION_REQUIRED = "permission_required"
    BENCHMARK_ONLY = "benchmark_only"
    DISABLED = "disabled"


class PortalMode(str, Enum):
    PRODUCTION_CANDIDATE_WITH_PERMISSION = "production_candidate_with_permission"
    BENCHMARK_ONLY_PERMISSION_REQUIRED = "benchmark_only_permission_required"
    FALLBACK = "fallback"
    DISABLED = "disabled"


@dataclass(slots=True)
class PortalListing:
    portal: str
    portal_mode: PortalMode
    city_query: str
    search_url: str
    page_number: int
    property_url: str
    address_raw: str = ""
    postcode_raw: str = ""
    city_raw: str = ""
    price_raw: str = ""
    status_raw: str = ""
    living_area_raw: str = ""
    rooms_raw: str = ""
    property_type_raw: str = ""
    broker_raw: str = ""
    image_url: str = ""
    source_evidence: str = ""


@dataclass(slots=True)
class PortalCityResult:
    portal: str
    portal_mode: PortalMode
    city_query: str
    search_url: str
    source_status: SourceStatus
    page_number: int = 1
    listings: list[PortalListing] = field(default_factory=list)
    duplicate_url_rate: float = 0.0
    fill_rates: dict[str, float] = field(default_factory=dict)
    blocked_reason: str = ""
    recommended_use: str = ""
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PortalSpikeResult:
    city_results: list[PortalCityResult]
    generated_at: str = ""
    report_title: str = "Portal Inventory Spike"
