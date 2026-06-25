from __future__ import annotations

import re
from dataclasses import dataclass

from domek_wonen.parsers.models import ParsedListing
from domek_wonen.qa.parser_output_gate import ParserFamilyQAResult, ParserListingQAResult


DECISION_ACTIVE_INVENTORY = "active_inventory"
DECISION_INACTIVE_STATUS = "inactive_status"
DECISION_UNSUPPORTED_TRANSACTION_TYPE = "unsupported_transaction_type"
DECISION_UNSUPPORTED_PROPERTY_TYPE = "unsupported_property_type"
DECISION_REVIEW = "review"

REASON_STATUS_AVAILABLE = "status_available"
REASON_STATUS_INACTIVE = "status_inactive"
REASON_STATUS_UNKNOWN = "status_unknown"
REASON_TRANSACTION_TYPE_UNSUPPORTED = "transaction_type_unsupported"
REASON_TRANSACTION_TYPE_UNKNOWN = "transaction_type_unknown"
REASON_PROPERTY_TYPE_ALLOWED = "property_type_allowed"
REASON_PROPERTY_TYPE_UNSUPPORTED = "property_type_unsupported"
REASON_PROPERTY_TYPE_UNKNOWN = "property_type_unknown"
REASON_QA_NOT_CLEAN = "qa_not_clean"
REASON_QA_REJECTED = "qa_rejected"

_TOKEN_SEPARATOR_PATTERN = re.compile(r"[\s\-_]+")

_UNKNOWN_TOKENS = frozenset({"", "unknown", "onbekend", "nvt", "n/a", "none", "null"})
_INACTIVE_STATUSES = frozenset({"onder_bod", "verkocht", "verhuurd"})
_ALLOWED_PROPERTY_TYPES = frozenset(
    {
        "house",
        "woning",
        "woonhuis",
        "eengezinswoning",
        "herenhuis",
        "tussenwoning",
        "hoekwoning",
        "vrijstaande_woning",
        "vrijstaand",
        "twee_onder_een_kap",
        "appartement",
        "apartment",
        "flat",
        "bovenwoning",
        "benedenwoning",
        "maisonette",
    }
)
_UNSUPPORTED_PROPERTY_TYPES = frozenset(
    {
        "kantoor",
        "office",
        "bedrijfspand",
        "commercial",
        "winkel",
        "horeca",
        "garage",
        "parkeerplaats",
        "parking",
        "parkeerplek",
        "grond",
        "bouwgrond",
        "land",
        "project",
        "nieuwbouwproject",
        "room",
        "kamer",
        "storage",
        "opslag",
    }
)


@dataclass(frozen=True, slots=True)
class InventoryEligibilityItem:
    listing: ParsedListing
    decision: str
    reasons: tuple[str, ...] = ()
    normalized_key: str = ""
    qa_status: str = ""


@dataclass(frozen=True, slots=True)
class InventoryEligibilityResult:
    active_inventory: tuple[InventoryEligibilityItem, ...]
    inactive_status: tuple[InventoryEligibilityItem, ...]
    unsupported_transaction_type: tuple[InventoryEligibilityItem, ...]
    unsupported_property_type: tuple[InventoryEligibilityItem, ...]
    review: tuple[InventoryEligibilityItem, ...]

    @property
    def active_count(self) -> int:
        return len(self.active_inventory)

    @property
    def inactive_status_count(self) -> int:
        return len(self.inactive_status)

    @property
    def unsupported_transaction_type_count(self) -> int:
        return len(self.unsupported_transaction_type)

    @property
    def unsupported_property_type_count(self) -> int:
        return len(self.unsupported_property_type)

    @property
    def review_count(self) -> int:
        return len(self.review)

    @property
    def total_count(self) -> int:
        return (
            self.active_count
            + self.inactive_status_count
            + self.unsupported_transaction_type_count
            + self.unsupported_property_type_count
            + self.review_count
        )


def evaluate_inventory_eligibility(
    qa_result: ParserFamilyQAResult,
) -> InventoryEligibilityResult:
    active_inventory: list[InventoryEligibilityItem] = []
    inactive_status: list[InventoryEligibilityItem] = []
    unsupported_transaction_type: list[InventoryEligibilityItem] = []
    unsupported_property_type: list[InventoryEligibilityItem] = []
    review: list[InventoryEligibilityItem] = []

    for qa_listing in qa_result.clean_listings:
        item = _evaluate_clean_listing(qa_listing)
        if item.decision == DECISION_ACTIVE_INVENTORY:
            active_inventory.append(item)
        elif item.decision == DECISION_INACTIVE_STATUS:
            inactive_status.append(item)
        elif item.decision == DECISION_UNSUPPORTED_TRANSACTION_TYPE:
            unsupported_transaction_type.append(item)
        elif item.decision == DECISION_UNSUPPORTED_PROPERTY_TYPE:
            unsupported_property_type.append(item)
        else:
            review.append(item)

    for qa_listing in qa_result.review_listings:
        review.append(
            _item_from_qa_listing(
                qa_listing,
                DECISION_REVIEW,
                (REASON_QA_NOT_CLEAN,),
            )
        )

    for qa_listing in qa_result.rejected_listings:
        review.append(
            _item_from_qa_listing(
                qa_listing,
                DECISION_REVIEW,
                (REASON_QA_REJECTED,),
            )
        )

    return InventoryEligibilityResult(
        active_inventory=tuple(active_inventory),
        inactive_status=tuple(inactive_status),
        unsupported_transaction_type=tuple(unsupported_transaction_type),
        unsupported_property_type=tuple(unsupported_property_type),
        review=tuple(review),
    )


def build_active_inventory_qa_result(qa_result: ParserFamilyQAResult) -> ParserFamilyQAResult:
    eligibility_result = evaluate_inventory_eligibility(qa_result)
    active_keys = {
        (id(item.listing), item.normalized_key)
        for item in eligibility_result.active_inventory
    }
    active_clean_listings = tuple(
        qa_listing
        for qa_listing in qa_result.clean_listings
        if (id(qa_listing.listing), qa_listing.normalized_key) in active_keys
    )

    return ParserFamilyQAResult(
        parser_family=qa_result.parser_family,
        source_id=qa_result.source_id,
        source_domain=qa_result.source_domain,
        clean_listings=active_clean_listings,
        review_listings=(),
        rejected_listings=(),
        total_count=len(active_clean_listings),
        clean_count=len(active_clean_listings),
        review_count=0,
        rejected_count=0,
        warnings=qa_result.warnings,
    )


def _evaluate_clean_listing(qa_listing: ParserListingQAResult) -> InventoryEligibilityItem:
    listing = qa_listing.listing
    transaction_type = _normalize_token(listing.transaction_type)
    if transaction_type in _UNKNOWN_TOKENS:
        return _item_from_qa_listing(
            qa_listing,
            DECISION_REVIEW,
            (REASON_TRANSACTION_TYPE_UNKNOWN,),
        )
    if transaction_type != "koop":
        return _item_from_qa_listing(
            qa_listing,
            DECISION_UNSUPPORTED_TRANSACTION_TYPE,
            (REASON_TRANSACTION_TYPE_UNSUPPORTED,),
        )

    status = _normalize_token(listing.status)
    if _is_inactive_status(status):
        return _item_from_qa_listing(
            qa_listing,
            DECISION_INACTIVE_STATUS,
            (REASON_STATUS_INACTIVE,),
        )
    if status != "beschikbaar":
        return _item_from_qa_listing(
            qa_listing,
            DECISION_REVIEW,
            (REASON_STATUS_UNKNOWN,),
        )

    property_type = _normalize_token(listing.property_type)
    if _is_unsupported_property_type(property_type):
        return _item_from_qa_listing(
            qa_listing,
            DECISION_UNSUPPORTED_PROPERTY_TYPE,
            (REASON_PROPERTY_TYPE_UNSUPPORTED,),
        )
    if not _is_allowed_property_type(property_type):
        return _item_from_qa_listing(
            qa_listing,
            DECISION_REVIEW,
            (REASON_PROPERTY_TYPE_UNKNOWN,),
        )

    return _item_from_qa_listing(
        qa_listing,
        DECISION_ACTIVE_INVENTORY,
        (REASON_STATUS_AVAILABLE, REASON_PROPERTY_TYPE_ALLOWED),
    )


def _item_from_qa_listing(
    qa_listing: ParserListingQAResult,
    decision: str,
    reasons: tuple[str, ...],
) -> InventoryEligibilityItem:
    return InventoryEligibilityItem(
        listing=qa_listing.listing,
        decision=decision,
        reasons=reasons,
        normalized_key=qa_listing.normalized_key,
        qa_status=qa_listing.qa_status,
    )


def _normalize_token(value: str) -> str:
    return _TOKEN_SEPARATOR_PATTERN.sub("_", (value or "").strip().casefold()).strip("_")


def _is_allowed_property_type(value: str) -> bool:
    return any(token in _ALLOWED_PROPERTY_TYPES for token in _property_type_tokens(value))


def _is_unsupported_property_type(value: str) -> bool:
    return any(token in _UNSUPPORTED_PROPERTY_TYPES for token in _property_type_tokens(value))


def _is_inactive_status(value: str) -> bool:
    return _normalize_token(value) in _INACTIVE_STATUSES


def _property_type_tokens(value: str) -> tuple[str, ...]:
    token = _normalize_token(value)
    compact_token = token.replace("_", "")
    if compact_token == token:
        return (token,)
    return (token, compact_token)
