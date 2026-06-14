from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class SourceCandidate:
    office_name: str
    website: str = ""
    root_domain: str = ""
    raw_place: str = ""
    normalized_place: str = ""
    gemeente: str = ""
    plaats: str = ""
    place_status: str = ""
    place_review_reason: str = ""
    provincie: str = ""
    aanbod_url: str = ""
    aanbod_url_quality: str = "missing"
    aanbod_url_type: str = "missing"
    aanbod_detection_method: str = "failed"
    aanbod_detection_score: int = 0
    aanbod_validation_reason: str = ""
    confidence: float = 0.0
    needs_review: bool = False
    website_resolution_status: str = ""
    source_adapter: str = "seed"
    source_origin: str = "seed"
    score: int = 0
    status: str = "missing"
    review_reason: str = ""
    rejection_reason: str = ""
    notes: str = ""
    osm_type: str = ""
    osm_id: str = ""
    osm_website: str = ""
    osm_contact_website: str = ""
    osm_city: str = ""
    osm_postcode: str = ""
    osm_phone: str = ""
    osm_contact_phone: str = ""
    osm_email: str = ""
    osm_contact_email: str = ""
    osm_lat: str = ""
    osm_lon: str = ""
    evidence: list[str] = field(default_factory=list)


@dataclass(slots=True)
class GeneratedQuery:
    gemeente: str
    query: str
    template: str
    provincie: str = ""


@dataclass(slots=True)
class DiscoveryResult:
    candidate: SourceCandidate
    score: int
    status: str
    reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class LiveAanbodAttempt:
    office_name: str
    website: str
    root_domain: str
    gemeente: str
    source_origin: str
    attempted: bool
    success: bool
    final_status: str
    final_aanbod_url: str
    detection_method: str
    detection_score: int
    failure_stage: str
    failure_reason: str
    http_status_homepage: int
    http_status_sitemap: int
    tested_urls_count: int
    best_candidate_url: str
    best_candidate_reason: str
    elapsed_ms: int


@dataclass(slots=True)
class AanbodAuditAttempt:
    office_name: str
    website: str
    root_domain: str
    gemeente: str
    final_status: str
    final_aanbod_url: str
    confidence: int
    detection_method: str
    homepage_status: int
    homepage_title: str
    candidates_found_count: int
    candidates_tested_count: int
    best_candidate_url: str
    final_page_type: str
    listing_signals_count: int
    residential_signals_count: int
    commercial_signals_count: int
    elapsed_ms: int = 0
    residential_signals_found: list[str] = field(default_factory=list)
    commercial_signals_found: list[str] = field(default_factory=list)
    page_quality_reason: str = ""
    listing_signals_found: list[str] = field(default_factory=list)
    commercial_hard_block: bool = False
    commercial_block_reason: str = ""
    is_duplicate_audit_result: bool = False
    rejection_reason: str = ""
