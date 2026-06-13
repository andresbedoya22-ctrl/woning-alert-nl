from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

import httpx

from .models import SourceCandidate
from .place_mapper import normalize_overpass_city


OVERPASS_QUERY_TEMPLATE = """[out:json][timeout:180];
area["name"="{province}"]["admin_level"="4"]["boundary"="administrative"]->.a;
(
node["office"="estate_agent"](area.a);
way["office"="estate_agent"](area.a);
relation["office"="estate_agent"](area.a);
node["shop"="estate_agent"](area.a);
way["shop"="estate_agent"](area.a);
relation["shop"="estate_agent"](area.a);
);
out center tags;
"""

PRIMARY_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
FALLBACK_OVERPASS_URL = "https://overpass.kumi.systems/api/interpreter"


@dataclass(slots=True)
class OverpassDiscoveryResponse:
    status: str
    candidates: list[SourceCandidate] = field(default_factory=list)
    raw_candidates: int = 0
    candidates_with_website: int = 0
    candidates_without_website: int = 0
    new_domains_added: int = 0
    duplicates_vs_seed: int = 0
    endpoint_used: str = ""
    errors: list[str] = field(default_factory=list)


def _normalize_url(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    return raw.rstrip("/")


def _extract_root_domain(value: str) -> str:
    parsed = urlsplit(value)
    host = (parsed.netloc or parsed.path).lower().strip()
    if host.startswith("www."):
        host = host[4:]
    if ":" in host:
        host = host.split(":", 1)[0]
    return host


class OverpassAdapter:
    def __init__(
        self,
        *,
        primary_url: str = PRIMARY_OVERPASS_URL,
        fallback_url: str = FALLBACK_OVERPASS_URL,
        timeout_seconds: float = 190.0,
        max_attempts: int = 3,
        backoff_seconds: float = 1.0,
        sleep_func: Any = time.sleep,
    ) -> None:
        self.primary_url = primary_url
        self.fallback_url = fallback_url
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self.backoff_seconds = backoff_seconds
        self.sleep_func = sleep_func

    def discover(self, province: str) -> OverpassDiscoveryResponse:
        query = OVERPASS_QUERY_TEMPLATE.format(province=province)
        errors: list[str] = []

        for index, url in enumerate((self.primary_url, self.fallback_url)):
            try:
                payload = self._post_query(url, query)
                candidates = self._parse_candidates(payload)
                status = "ok" if index == 0 else "ok_fallback"
                with_website = sum(1 for candidate in candidates if candidate.website)
                without_website = len(candidates) - with_website
                return OverpassDiscoveryResponse(
                    status=status,
                    candidates=candidates,
                    raw_candidates=len(candidates),
                    candidates_with_website=with_website,
                    candidates_without_website=without_website,
                    endpoint_used=url,
                    errors=errors,
                )
            except Exception as exc:  # pragma: no cover - exercised via tests on status
                errors.append(f"{url}: {exc}")

        return OverpassDiscoveryResponse(status="failed", endpoint_used="", errors=errors)

    def _post_query(self, url: str, query: str) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.post(
                        url,
                        content=query.encode("utf-8"),
                        headers={"Content-Type": "text/plain; charset=utf-8"},
                    )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("Overpass response is not a JSON object")
                return payload
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt < self.max_attempts:
                    self.sleep_func(self.backoff_seconds * attempt)

        raise RuntimeError(f"Overpass request failed after {self.max_attempts} attempts: {last_error}")

    def _parse_candidates(self, payload: dict[str, Any]) -> list[SourceCandidate]:
        elements = payload.get("elements", [])
        if not isinstance(elements, list):
            raise ValueError("Overpass payload missing elements list")

        candidates: list[SourceCandidate] = []
        for element in elements:
            if not isinstance(element, dict):
                continue

            tags = element.get("tags", {})
            if not isinstance(tags, dict):
                tags = {}

            website = _normalize_url(tags.get("website") or tags.get("contact:website"))
            city = (tags.get("addr:city") or "").strip()
            place_mapping = normalize_overpass_city(city)
            postcode = (tags.get("addr:postcode") or "").strip()
            lat, lon = self._extract_lat_lon(element)
            notes = " | ".join(
                part
                for part in (
                    f"osm_type={element.get('type', '')}",
                    f"osm_id={element.get('id', '')}",
                    f"website={tags.get('website', '')}",
                    f"contact_website={tags.get('contact:website', '')}",
                    f"phone={tags.get('phone', '')}",
                    f"contact_phone={tags.get('contact:phone', '')}",
                    f"email={tags.get('email', '')}",
                    f"contact_email={tags.get('contact:email', '')}",
                    f"raw_addr_city={city}",
                    f"normalized_place={place_mapping['normalized_place']}",
                    f"normalized_gemeente={place_mapping['gemeente']}",
                    f"place_status={place_mapping['place_status']}",
                    f"postcode={postcode}",
                    f"lat={lat}",
                    f"lon={lon}",
                )
                if part and not part.endswith("=")
            )

            candidates.append(
                SourceCandidate(
                    office_name=(tags.get("name") or "").strip(),
                    website=website,
                    root_domain=_extract_root_domain(website) if website else "",
                    raw_place=place_mapping["raw_place"],
                    normalized_place=place_mapping["normalized_place"],
                    gemeente=place_mapping["gemeente"],
                    plaats=city,
                    place_status=place_mapping["place_status"],
                    place_review_reason=place_mapping["review_reason"],
                    provincie="Noord-Brabant",
                    confidence=0.50,
                    needs_review=True,
                    source_adapter="overpass",
                    source_origin="overpass_osm",
                    review_reason="overpass candidate requires validation",
                    notes=notes,
                    osm_type=str(element.get("type") or ""),
                    osm_id=str(element.get("id") or ""),
                    osm_website=(tags.get("website") or "").strip(),
                    osm_contact_website=(tags.get("contact:website") or "").strip(),
                    osm_city=city,
                    osm_postcode=postcode,
                    osm_phone=(tags.get("phone") or "").strip(),
                    osm_contact_phone=(tags.get("contact:phone") or "").strip(),
                    osm_email=(tags.get("email") or "").strip(),
                    osm_contact_email=(tags.get("contact:email") or "").strip(),
                    osm_lat=lat,
                    osm_lon=lon,
                )
            )

        return candidates

    @staticmethod
    def _extract_lat_lon(element: dict[str, Any]) -> tuple[str, str]:
        if "lat" in element and "lon" in element:
            return str(element.get("lat") or ""), str(element.get("lon") or "")

        center = element.get("center", {})
        if isinstance(center, dict):
            return str(center.get("lat") or ""), str(center.get("lon") or "")

        return "", ""
