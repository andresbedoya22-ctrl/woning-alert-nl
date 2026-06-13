from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class PropertySource:
    source_id: str
    office_name: str
    root_domain: str
    website: str
    aanbod_url: str
    gemeente: str
    province: str
    legal_status: str
    aanbod_url_quality: str
    is_active: bool
    source_origin: str = ""


@dataclass(slots=True)
class CrawlResult:
    source: PropertySource
    ok: bool
    final_url: str = ""
    html: str = ""
    error: str = ""
    elapsed_ms: int = 0


@dataclass(slots=True)
class PropertyCandidate:
    source_id: str
    source_url: str
    root_domain: str
    gemeente: str
    property_url: str
    title: str = ""
    address_raw: str = ""
    city_raw: str = ""
    price_raw: str = ""
    status_raw: str = ""
    living_area_raw: str = ""
    plot_area_raw: str = ""
    rooms_raw: str = ""
    image_url: str = ""
    extraction_confidence: float = 0.0
    needs_review: bool = False
    review_reason: str = ""


@dataclass(slots=True)
class PropertyInventoryRecord:
    property_id: str
    source_id: str
    source_root_domain: str
    source_aanbod_url: str
    property_url: str
    title: str
    address_raw: str
    city_raw: str
    gemeente: str
    price_raw: str
    price_eur: str
    status: str
    status_raw: str
    living_area_raw: str
    plot_area_raw: str
    rooms_raw: str
    image_url: str
    first_seen_at: str
    last_seen_at: str
    discovery_run_id: str
    extraction_confidence: str
    needs_review: str
    review_reason: str


@dataclass(slots=True)
class PropertyDiscoveryRunOutput:
    run_id: str
    run_dir: Path
    latest_dir: Path
    report_path: Path
    sources_loaded: int
    sources_attempted: int
    sources_succeeded: int
    sources_failed: int
    total_property_candidates: int
    deduped_properties: int
