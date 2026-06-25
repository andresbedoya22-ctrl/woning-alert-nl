from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ParserInput:
    source_id: str
    source_domain: str
    source_url: str
    content: str
    content_type: str = "html"
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ParsedListing:
    source_id: str
    source_domain: str
    canonical_url: str
    address_raw: str = ""
    street: str = ""
    house_number: str = ""
    postcode: str = ""
    city: str = ""
    asking_price_eur: int | None = None
    transaction_type: str = "unknown"
    status: str = "unknown"
    living_area_m2: int | None = None
    plot_area_m2: int | None = None
    rooms_count: int | None = None
    bedrooms_count: int | None = None
    property_type: str = ""
    energy_label: str = ""
    evidence: tuple[str, ...] = ()
    confidence_score: float = 0.0
    needs_review: bool = False
    review_reason: str = ""


@dataclass(frozen=True, slots=True)
class ParserFamilyResult:
    parser_family: str
    source_id: str
    source_domain: str
    listings: tuple[ParsedListing, ...]
    rejected_count: int = 0
    warning_count: int = 0
    warnings: tuple[str, ...] = ()
