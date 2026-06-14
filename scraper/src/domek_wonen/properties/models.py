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
    aanbod_url_type: str = "missing"
    source_quality_status: str = ""
    source_quality_reason: str = ""
    source_origin: str = ""


@dataclass(slots=True)
class CrawlResult:
    source: PropertySource
    ok: bool
    final_url: str = ""
    html: str = ""
    error: str = ""
    elapsed_ms: int = 0
    timed_out: bool = False


@dataclass(slots=True)
class PropertyCandidate:
    source_id: str
    source_url: str
    root_domain: str
    gemeente: str
    property_url: str
    candidate_type: str = ""
    link_text: str = ""
    extraction_method: str = ""
    excluded_reason: str = ""
    is_property_like: bool = False
    property_url_classification: str = ""
    title: str = ""
    address_raw: str = ""
    city_raw: str = ""
    price_raw: str = ""
    status_raw: str = ""
    living_area_raw: str = ""
    plot_area_raw: str = ""
    rooms_raw: str = ""
    energy_label: str = ""
    image_url: str = ""
    extraction_source: str = "card"
    detail_extraction_status: str = "skipped"
    detail_error: str = ""
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
    energy_label: str
    image_url: str
    extraction_source: str
    detail_extraction_status: str
    detail_error: str
    first_seen_at: str
    last_seen_at: str
    discovery_run_id: str
    extraction_confidence: str
    needs_review: str
    review_reason: str


@dataclass(slots=True)
class PropertyRejectedRecord:
    source_id: str
    root_domain: str
    source_url: str
    property_url: str
    title: str
    address_raw: str
    city_raw: str
    gemeente: str
    price_raw: str
    status_raw: str
    living_area_raw: str
    plot_area_raw: str
    rooms_raw: str
    energy_label: str
    image_url: str
    rejection_reason: str
    extraction_source: str
    detail_extraction_status: str
    detail_error: str
    extraction_confidence: str
    needs_review: str
    review_reason: str
    candidate_type: str
    link_text: str
    extraction_method: str
    excluded_reason: str
    is_property_like: str
    property_url_classification: str


@dataclass(slots=True)
class PropertyDiscoveryRunOutput:
    run_id: str
    run_dir: Path
    latest_dir: Path
    report_path: Path
    run_status: str
    started_at: str
    finished_at: str
    duration_seconds: float
    sources_loaded: int
    sources_attempted: int
    sources_succeeded: int
    sources_failed: int
    sources_timeout: int
    sources_skipped_invalid_aanbod_url: int
    total_property_candidates: int
    deduped_properties: int
    rejected_candidates: int
