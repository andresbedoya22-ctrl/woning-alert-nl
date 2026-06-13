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
    confidence: float = 0.0
    needs_review: bool = False
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
