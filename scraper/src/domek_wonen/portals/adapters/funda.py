from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import quote_plus

from domek_wonen.portals.models import PortalListing, PortalMode
from domek_wonen.portals.portal_inventory_spike import normalize_text

portal_name = "funda"
portal_mode = PortalMode.BENCHMARK_ONLY_PERMISSION_REQUIRED


class _FundaHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.cards: list[dict[str, str]] = []
        self._card: dict[str, str] | None = None
        self._depth = 0
        self._field = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value or "" for key, value in attrs}
        class_name = attributes.get("class", "")
        if tag == "div" and "search-result" in class_name:
            self._card = {}
            self.cards.append(self._card)
            self._depth = 1
            return
        if self._card is None:
            return
        self._depth += 1

        field_map = {
            "search-result__header-title-col": "address_raw",
            "search-result__header-subtitle-col": "city_raw",
            "search-result-price": "price_raw",
            "search-result-kenmerken-woonopp": "living_area_raw",
            "search-result-kenmerken-aantalkamers": "rooms_raw",
            "search-result__property-type": "property_type_raw",
            "search-result-status": "status_raw",
            "search-result-broker": "broker_raw",
            "source-evidence": "source_evidence",
        }

        if tag == "img":
            self._card["image_url"] = attributes.get("src", "")
        if tag == "a" and "search-result__header-title-container" in class_name:
            self._card["property_url"] = attributes.get("href", "")
        for marker, field_name in field_map.items():
            if marker in class_name:
                self._field = field_name
                break

    def handle_endtag(self, tag: str) -> None:
        if self._card is None:
            return
        self._depth -= 1
        if self._depth <= 0:
            self._card = None
        self._field = ""

    def handle_data(self, data: str) -> None:
        if self._card is None or not self._field:
            return
        self._card[self._field] = normalize_text(self._card.get(self._field, "") + " " + data)


def build_search_url(city: str, page: int = 1) -> str:
    url = f"https://www.funda.nl/zoeken/koop?selected_area=%5B%22{quote_plus(normalize_text(city).lower())}%22%5D"
    if page > 1:
        return f"{url}&page={page}"
    return url


def parse_listing_cards(html: str, city_query: str, search_url: str, page_number: int) -> list[PortalListing]:
    parser = _FundaHTMLParser()
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
