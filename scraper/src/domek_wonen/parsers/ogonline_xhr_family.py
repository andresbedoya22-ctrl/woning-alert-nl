from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from .models import ParsedListing, ParserFamilyResult, ParserInput


_WHITESPACE_PATTERN = re.compile(r"\s+")


class OGonlineXHRParserFamily:
    parser_family = "ogonline_xhr"

    def parse_api_response(self, parser_input: ParserInput) -> ParserFamilyResult:
        try:
            payload = json.loads(parser_input.content or "")
        except json.JSONDecodeError:
            return _warning_result(parser_input, "invalid_json")

        if not isinstance(payload, dict) or "docs" not in payload:
            return _warning_result(parser_input, "missing_docs")

        docs = payload.get("docs")
        if not isinstance(docs, list):
            return _warning_result(parser_input, "invalid_docs")

        listings: list[ParsedListing] = []
        rejected_count = 0
        for doc in docs:
            if not isinstance(doc, dict):
                rejected_count += 1
                continue

            listing = _parse_doc(parser_input, doc)
            if listing is None:
                rejected_count += 1
                continue
            listings.append(listing)

        warnings = ("no_ogonline_docs_parsed",) if not listings and docs else ()
        return ParserFamilyResult(
            parser_family=self.parser_family,
            source_id=parser_input.source_id,
            source_domain=parser_input.source_domain,
            listings=tuple(listings),
            rejected_count=rejected_count,
            warning_count=len(warnings),
            warnings=warnings,
        )


def parse_ogonline_xhr_api_response(parser_input: ParserInput) -> ParserFamilyResult:
    return OGonlineXHRParserFamily().parse_api_response(parser_input)


def _warning_result(parser_input: ParserInput, warning: str) -> ParserFamilyResult:
    return ParserFamilyResult(
        parser_family=OGonlineXHRParserFamily.parser_family,
        source_id=parser_input.source_id,
        source_domain=parser_input.source_domain,
        listings=(),
        rejected_count=0,
        warning_count=1,
        warnings=(warning,),
    )


def _parse_doc(parser_input: ParserInput, doc: dict[str, Any]) -> ParsedListing | None:
    doc_id = _text(_first(doc, ("id", "objectId", "object_id", "listingId", "listing_id")))
    slug = _text(_first(doc, ("slug", "urlSlug", "url_slug")))
    canonical_url = _canonical_url(parser_input.source_domain, _detail_url(doc), doc_id, slug)
    street = _text(_first_nested(doc, ("street", "street_name", "streetName")))
    house_number = _text(_first_nested(doc, ("house_number", "houseNumber", "number", "housenumber")))
    address_raw = _address_raw(doc, street, house_number)
    postcode = _text(_first_nested(doc, ("postcode", "postal_code", "postalCode", "zip"))).replace(" ", "").upper()
    city = _extract_city(doc)
    asking_price_eur = _extract_asking_price_eur(doc)
    transaction_type = _transaction_type(doc)
    status = _normalize_ogonline_status(_first_nested(doc, ("status", "availability", "saleStatus", "sale_status")))
    living_area_m2 = _int_value(_first_nested(doc, ("livingArea", "living_area", "areaLiving", "area_living")))
    rooms_count = _int_value(_first_nested(doc, ("rooms", "room_count", "numberOfRooms", "aantalKamers")))
    bedrooms_count = _int_value(_first_nested(doc, ("bedrooms", "bedroom_count", "numberOfBedrooms", "aantalSlaapkamers")))
    property_type = _text(_first_nested(doc, ("type", "objectType", "propertyType", "property_type")))
    energy_label = _text(_first_nested(doc, ("energyLabel", "energy_label", "label"))).upper()

    if not any((canonical_url, doc_id, slug, address_raw, postcode)):
        return None

    needs_review, review_reason = _review_state(
        canonical_url=canonical_url,
        address_raw=address_raw,
        city=city,
        asking_price_eur=asking_price_eur,
    )

    return ParsedListing(
        source_id=parser_input.source_id,
        source_domain=parser_input.source_domain,
        canonical_url=canonical_url,
        address_raw=address_raw,
        street=street,
        house_number=house_number,
        postcode=postcode,
        city=city,
        asking_price_eur=asking_price_eur,
        transaction_type=transaction_type,
        status=status,
        living_area_m2=living_area_m2,
        rooms_count=rooms_count,
        bedrooms_count=bedrooms_count,
        property_type=property_type,
        energy_label=energy_label,
        evidence=_evidence(doc_id=doc_id, image_count=_image_count(doc), status=status),
        confidence_score=_confidence_score(
            canonical_url=canonical_url,
            address_raw=address_raw,
            city=city,
            asking_price_eur=asking_price_eur,
            status=status,
            living_area_m2=living_area_m2,
            rooms_count=rooms_count,
        ),
        needs_review=needs_review,
        review_reason=review_reason,
    )


def _first(doc: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in doc:
            return doc[key]
    return None


def _first_nested(doc: dict[str, Any], keys: tuple[str, ...]) -> Any:
    direct = _first(doc, keys)
    if direct is not None:
        return direct
    for key in ("address", "location", "price", "salesPrice", "details", "web"):
        value = doc.get(key)
        if isinstance(value, dict):
            nested = _first(value, keys)
            if nested is not None:
                return nested
    return None


def _detail_url(doc: dict[str, Any]) -> str:
    direct = _text(_first(doc, ("url", "detail_url", "detailUrl", "link", "permalink", "canonical_url")))
    if direct:
        return direct
    for key in ("links", "web"):
        value = doc.get(key)
        if isinstance(value, dict):
            nested = _text(_first(value, ("url", "detail", "detailUrl", "href", "permalink")))
            if nested:
                return nested
    return ""


def _canonical_url(source_domain: str, detail_url: str, doc_id: str, slug: str) -> str:
    cleaned = _collapse_whitespace(detail_url)
    if cleaned.startswith(("http://", "https://")):
        return cleaned.rstrip("/")

    domain = (source_domain or "").strip().lower()
    if not domain:
        return ""

    if cleaned.startswith("/"):
        return f"https://{domain}{cleaned.rstrip('/')}"
    if cleaned:
        return f"https://{domain}/{cleaned.strip('/')}"

    stable_segment = slug or doc_id
    if stable_segment:
        return f"https://{domain}/aanbod/wonen/{stable_segment.strip('/')}"
    return ""


def _address_raw(doc: dict[str, Any], street: str, house_number: str) -> str:
    address = doc.get("address")
    if isinstance(address, str):
        return _collapse_whitespace(address)
    if isinstance(address, dict):
        text = _text(_first(address, ("display", "label", "formatted", "address", "addressLine")))
        if text:
            return text
    return _collapse_whitespace(" ".join(part for part in (street, house_number) if part))


def _extract_city(doc: Mapping[str, Any]) -> str:
    for path in (
        ("city",),
        ("place",),
        ("address", "city"),
        ("address", "settlement"),
        ("location", "city"),
        ("location", "place"),
        ("place", "name"),
        ("municipality", "name"),
        ("address", "place"),
        ("plaats",),
        ("locality",),
    ):
        value = _path_value(doc, path)
        if isinstance(value, Mapping):
            value = _first_mapping_value(value, ("name", "city", "place", "plaats"))
        text = _text(value)
        if text:
            return text
    return ""


def _extract_asking_price_eur(doc: Mapping[str, Any]) -> int | None:
    for path in (
        ("asking_price_eur",),
        ("askingPrice",),
        ("purchasePrice",),
        ("price",),
        ("price", "amount"),
        ("price", "value"),
        ("financial", "price"),
        ("financial", "askingPrice"),
        ("salesPrice",),
        ("salesPrice", "amount"),
        ("salesPrice", "value"),
    ):
        value = _path_value(doc, path)
        parent_value = _path_value(doc, path[:-1]) if len(path) > 1 else None
        if _looks_like_rent_price(path, value) or _looks_like_rent_price(path[:-1], parent_value):
            continue
        parsed = _int_value(value)
        if parsed is not None:
            return parsed
    return None


def _normalize_ogonline_status(raw_status: Any) -> str:
    normalized = _text(raw_status).casefold().replace("-", "_").replace(" ", "_")
    if normalized in {"available", "beschikbaar", "active", "for_sale"}:
        return "beschikbaar"
    if normalized in {
        "reserved",
        "under_bid",
        "under_offer",
        "onder_bod",
        "under_option",
        "verkocht_onder_voorbehoud",
    }:
        return "onder_bod"
    if normalized in {"sold", "verkocht"}:
        return "verkocht"
    if normalized in {"rented", "verhuurd"}:
        return "verhuurd"
    return "unknown"


def _transaction_type(doc: dict[str, Any]) -> str:
    if doc.get("isSales") is True:
        return "koop"
    if doc.get("isRentals") is True:
        return "huur"
    text = " ".join(_text(value) for value in (_first(doc, ("market", "transaction", "transactionType")), doc.get("category")))
    normalized = text.casefold()
    if any(signal in normalized for signal in ("sale", "sales", "koop", "consumer")):
        return "koop"
    if any(signal in normalized for signal in ("rent", "rental", "huur")):
        return "huur"
    return "unknown"


def _image_count(doc: dict[str, Any]) -> int | None:
    value = _first(doc, ("photos", "images", "pictures", "media"))
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        for key in ("photos", "images", "items", "data"):
            nested = value.get(key)
            if isinstance(nested, list):
                return len(nested)
    return None


def _review_state(
    *,
    canonical_url: str,
    address_raw: str,
    city: str,
    asking_price_eur: int | None,
) -> tuple[bool, str]:
    reasons: list[str] = []
    if not canonical_url:
        reasons.append("missing_canonical_url")
    if not address_raw:
        reasons.append("missing_address")
    if asking_price_eur is None:
        reasons.append("missing_price")
    if not city:
        reasons.append("missing_city")
    return bool(reasons), ",".join(reasons)


def _evidence(*, doc_id: str, image_count: int | None, status: str) -> tuple[str, ...]:
    signals = ["ogonline_xhr"]
    if doc_id:
        signals.append(f"doc_id:{doc_id}")
    if status != "unknown":
        signals.append(f"status:{status}")
    if image_count is not None:
        signals.append(f"image_count:{image_count}")
    return tuple(signals)


def _confidence_score(
    *,
    canonical_url: str,
    address_raw: str,
    city: str,
    asking_price_eur: int | None,
    status: str,
    living_area_m2: int | None,
    rooms_count: int | None,
) -> float:
    score = 0.0
    if canonical_url:
        score += 0.30
    if address_raw:
        score += 0.20
    if asking_price_eur is not None:
        score += 0.15
    if city:
        score += 0.10
    if status != "unknown":
        score += 0.10
    if living_area_m2 is not None:
        score += 0.10
    if rooms_count is not None:
        score += 0.05
    return round(max(0.0, min(score, 1.0)), 2)


def _int_value(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, dict):
        for key in ("amount", "value", "price"):
            parsed = _int_value(value.get(key))
            if parsed is not None:
                return parsed
        return None
    if isinstance(value, str):
        digits = re.sub(r"[^\d]", "", value)
        return int(digits) if digits else None
    return None


def _path_value(value: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = value
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


def _first_mapping_value(value: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in value:
            return value[key]
    return None


def _looks_like_rent_price(path: tuple[str, ...], value: Any) -> bool:
    path_text = ".".join(path).casefold()
    if any(signal in path_text for signal in ("rent", "huur")):
        return True
    if not isinstance(value, Mapping):
        return False
    combined = " ".join(
        _text(value.get(key)).casefold()
        for key in ("type", "transactionType", "transaction", "period", "frequency", "unit")
    )
    return any(signal in combined for signal in ("rent", "rental", "huur", "month", "maand"))


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float)):
        return _collapse_whitespace(str(value))
    return ""


def _collapse_whitespace(value: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", value or "").strip()
