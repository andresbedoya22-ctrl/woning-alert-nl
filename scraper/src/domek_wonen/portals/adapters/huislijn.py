from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import quote_plus

from domek_wonen.portals.models import PortalListing, PortalMode
from domek_wonen.portals.portal_inventory_spike import normalize_text

portal_name = "huislijn"
portal_mode = PortalMode.PRODUCTION_CANDIDATE_WITH_PERMISSION


class _CardHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.cards: list[dict[str, str]] = []
        self._stack: list[tuple[str, dict[str, str]]] = []
        self._field: str = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value or "" for key, value in attrs}
        class_name = attributes.get("class", "")
        if tag == "article" and "listing-card" in class_name:
            card = {"property_url": attributes.get("data-url", "")}
            self.cards.append(card)
            self._stack.append((tag, card))
            return
        if not self._stack:
            return

        current_card = self._stack[-1][1]
        field_map = {
            "address": "address_raw",
            "postcode": "postcode_raw",
            "city": "city_raw",
            "price": "price_raw",
            "status": "status_raw",
            "area": "living_area_raw",
            "rooms": "rooms_raw",
            "type": "property_type_raw",
            "broker": "broker_raw",
            "evidence": "source_evidence",
        }
        if tag == "img":
            current_card["image_url"] = attributes.get("src", "")
        elif tag == "a" and "listing-link" in class_name:
            current_card["property_url"] = attributes.get("href", "")
        else:
            for marker, field_name in field_map.items():
                if marker in class_name:
                    self._field = field_name
                    break

    def handle_endtag(self, tag: str) -> None:
        if self._stack and tag == self._stack[-1][0]:
            self._stack.pop()
        self._field = ""

    def handle_data(self, data: str) -> None:
        if not self._stack or not self._field:
            return
        current_card = self._stack[-1][1]
        current_card[self._field] = normalize_text(current_card.get(self._field, "") + " " + data)


def build_search_url(city: str, page: int = 1) -> str:
    url = f"https://www.huislijn.nl/koopwoning/nederland/{quote_plus(normalize_text(city).lower())}"
    if page > 1:
        return f"{url}?page={page}"
    return url


def parse_listing_cards(html: str, city_query: str, search_url: str, page_number: int) -> list[PortalListing]:
    parser = _CardHTMLParser()
    parser.feed(html)
    listings: list[PortalListing] = []
    for card in parser.cards:
        listings.append(
            PortalListing(
                portal=portal_name,
                portal_mode=portal_mode,
                city_query=city_query,
                search_url=search_url,
                page_number=page_number,
                property_url=card.get("property_url", ""),
                address_raw=card.get("address_raw", ""),
                postcode_raw=card.get("postcode_raw", ""),
                city_raw=card.get("city_raw", ""),
                price_raw=card.get("price_raw", ""),
                status_raw=card.get("status_raw", ""),
                living_area_raw=card.get("living_area_raw", ""),
                rooms_raw=card.get("rooms_raw", ""),
                property_type_raw=card.get("property_type_raw", ""),
                broker_raw=card.get("broker_raw", ""),
                image_url=card.get("image_url", ""),
                source_evidence=card.get("source_evidence", ""),
            )
        )
    return listings
