from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Any
from urllib.parse import urlsplit, urlunsplit


SourceAccessState = str
TransactionType = str
ListingStatus = str
InventoryChangeType = str


def _clean_text(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def _lower_clean(value: str | None) -> str:
    return _clean_text(value).lower()


def normalize_inventory_url(url: str | None) -> str:
    """Return a stable URL key for inventory comparisons.

    The inventory core should not treat `http://x/a/` and `https://x/a` as
    different properties. Query strings and fragments are intentionally removed
    because many listing sites add tracking parameters.
    """
    cleaned = _clean_text(url)
    if not cleaned:
        return ""

    parsed = urlsplit(cleaned)
    scheme = "https" if parsed.scheme in {"http", "https"} else parsed.scheme
    netloc = parsed.netloc.lower()
    path = "/".join(segment for segment in parsed.path.split("/") if segment)
    normalized_path = f"/{path}" if path else ""
    return urlunsplit((scheme, netloc, normalized_path, "", ""))


def stable_hash(parts: list[str]) -> str:
    payload = "|".join(_clean_text(part).lower() for part in parts)
    return sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class InventorySource:
    source_id: str
    source_domain: str
    source_name: str = ""
    access_status: SourceAccessState = "candidate"
    delivery_mode: str = "unknown_manual_review"
    parser_family: str = ""
    last_success_at: str = ""
    last_failure_at: str = ""
    failure_reason: str = ""

    @property
    def can_run(self) -> bool:
        return self.access_status in {"allowed", "limited"}


@dataclass(frozen=True, slots=True)
class RawListing:
    source_id: str
    source_domain: str
    source_url: str
    raw_id: str = ""
    fetched_at: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def stable_key(self) -> str:
        if self.raw_id:
            return stable_hash([self.source_domain, self.raw_id])
        return stable_hash([self.source_domain, normalize_inventory_url(self.source_url)])


@dataclass(frozen=True, slots=True)
class NormalizedListing:
    source_id: str
    source_domain: str
    canonical_url: str
    address_raw: str = ""
    street: str = ""
    house_number: str = ""
    postcode: str = ""
    city: str = ""
    asking_price_eur: int | None = None
    transaction_type: TransactionType = "unknown"
    status: ListingStatus = "unknown"
    living_area_m2: int | None = None
    plot_area_m2: int | None = None
    rooms_count: int | None = None
    bedrooms_count: int | None = None
    energy_label: str = ""
    property_type: str = ""
    external_id: str = ""
    content_hash: str = ""
    confidence_score: float = 0.0
    first_seen_at: str = ""
    last_seen_at: str = ""
    evidence: str = ""
    needs_review: bool = False
    review_reason: str = ""

    def normalized_url(self) -> str:
        return normalize_inventory_url(self.canonical_url)

    def stable_key(self) -> str:
        """Build a deterministic identity key for cross-day comparison.

        Prefer source-domain + canonical URL. If URL is missing, fall back to a
        property-like address key. This fallback is intentionally conservative:
        it includes city and price to reduce accidental merges.
        """
        normalized_url = self.normalized_url()
        if normalized_url:
            return stable_hash([self.source_domain, normalized_url])

        if self.external_id:
            return stable_hash([self.source_domain, self.external_id])

        return stable_hash(
            [
                self.address_raw,
                self.street,
                self.house_number,
                self.postcode,
                self.city,
                str(self.asking_price_eur or ""),
            ]
        )

    def comparable_hash(self) -> str:
        """Hash fields that matter for inventory change detection."""
        if self.content_hash:
            return self.content_hash
        return stable_hash(
            [
                self.normalized_url(),
                self.address_raw,
                self.city,
                str(self.asking_price_eur or ""),
                self.transaction_type,
                self.status,
                str(self.living_area_m2 or ""),
                str(self.rooms_count or ""),
                str(self.bedrooms_count or ""),
                self.energy_label,
            ]
        )

    def to_inventory_item(self) -> "InventoryItem":
        return InventoryItem(
            inventory_id=self.stable_key(),
            source_id=self.source_id,
            source_domain=self.source_domain,
            canonical_url=self.normalized_url(),
            address_raw=_clean_text(self.address_raw),
            city=_clean_text(self.city),
            asking_price_eur=self.asking_price_eur,
            transaction_type=self.transaction_type,
            status=self.status,
            first_seen_at=self.first_seen_at,
            last_seen_at=self.last_seen_at,
            comparable_hash=self.comparable_hash(),
            confidence_score=self.confidence_score,
            needs_review=self.needs_review,
            review_reason=self.review_reason,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class InventoryItem:
    inventory_id: str
    source_id: str
    source_domain: str
    canonical_url: str
    address_raw: str
    city: str
    asking_price_eur: int | None
    transaction_type: TransactionType
    status: ListingStatus
    first_seen_at: str
    last_seen_at: str
    comparable_hash: str
    confidence_score: float = 0.0
    needs_review: bool = False
    review_reason: str = ""


@dataclass(frozen=True, slots=True)
class InventorySnapshot:
    snapshot_id: str
    captured_at: str
    listings: tuple[NormalizedListing, ...]
    source_failures: dict[str, str] = field(default_factory=dict)

    def by_stable_key(self) -> dict[str, NormalizedListing]:
        """Deduplicate listings within a snapshot by stable key.

        If a parser produces duplicates, keep the listing with the highest
        confidence score, then the one with the richest comparable hash data.
        """
        selected: dict[str, NormalizedListing] = {}
        for listing in self.listings:
            key = listing.stable_key()
            current = selected.get(key)
            if current is None or _is_better_listing(listing, current):
                selected[key] = listing
        return selected


@dataclass(frozen=True, slots=True)
class InventoryChange:
    change_type: InventoryChangeType
    inventory_id: str
    before: NormalizedListing | None = None
    after: NormalizedListing | None = None
    changed_fields: tuple[str, ...] = ()
    reason: str = ""


@dataclass(frozen=True, slots=True)
class InventoryDiffResult:
    previous_snapshot_id: str
    current_snapshot_id: str
    changes: tuple[InventoryChange, ...]
    source_failures: dict[str, str] = field(default_factory=dict)

    def changes_by_type(self, change_type: InventoryChangeType) -> tuple[InventoryChange, ...]:
        return tuple(change for change in self.changes if change.change_type == change_type)

    def counts_by_type(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for change in self.changes:
            counts[change.change_type] = counts.get(change.change_type, 0) + 1
        return counts


def _is_better_listing(candidate: NormalizedListing, current: NormalizedListing) -> bool:
    if candidate.confidence_score != current.confidence_score:
        return candidate.confidence_score > current.confidence_score

    candidate_richness = _listing_richness(candidate)
    current_richness = _listing_richness(current)
    return candidate_richness > current_richness


def _listing_richness(listing: NormalizedListing) -> int:
    fields = [
        listing.address_raw,
        listing.city,
        str(listing.asking_price_eur or ""),
        listing.status,
        listing.transaction_type,
        str(listing.living_area_m2 or ""),
        str(listing.rooms_count or ""),
        str(listing.bedrooms_count or ""),
        listing.energy_label,
    ]
    return sum(1 for value in fields if _clean_text(value))
