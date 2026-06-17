from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse


CLASSIFICATIONS = (
    "property_detail_candidate",
    "listing_index",
    "service_page",
    "office_page",
    "contact_page",
    "blog_news",
    "commercial_page",
    "legal_page",
    "unknown_non_property",
)

EXACT_INDEX_PATHS = {
    "aanbod",
    "woningaanbod",
    "succesvol-verkocht",
    "nieuwbouw",
}
SERVICE_SEGMENTS = {
    "huis-verkopen",
    "verkopen",
    "diensten",
    "aankoop",
    "aankoopmakelaar",
    "taxatie",
}
OFFICE_SEGMENTS = {"over-ons", "team", "vacatures"}
CONTACT_SEGMENTS = {"contact"}
BLOG_SEGMENTS = {"nieuws", "blog"}
LEGAL_SEGMENTS = {"privacy", "algemene-voorwaarden"}
COMMERCIAL_SEGMENTS = {"bedrijfspand", "bedrijfsruimte", "horeca", "kantoor", "winkel", "belegging"}
DETAIL_PREFIXES = {"aanbod", "woning", "huis-kopen"}
ADDRESS_OR_ID_PATTERN = re.compile(
    r"(\d{3,}([a-z]{0,3})?$)|(\d{4}\s?[a-z]{2})|([a-z]+(?:-[a-z0-9]+){2,})",
    flags=re.IGNORECASE,
)
_OGONLINE_DETAIL_ID_PATTERN = re.compile(r"^[a-z0-9]{8,}$", flags=re.IGNORECASE)
_ADDRESS_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*-\d+[a-z0-9/-]*$", flags=re.IGNORECASE)


@dataclass(slots=True)
class PropertyUrlClassification:
    classification: str
    is_property_like: bool
    excluded_reason: str = ""


class PropertyUrlClassifier:
    def classify(self, url: str, root_domain: str = "") -> PropertyUrlClassification:
        parsed = urlparse((url or "").strip())
        hostname = (parsed.hostname or "").lower()
        normalized_root = (root_domain or "").strip().lower()
        segments = [segment.lower() for segment in parsed.path.split("/") if segment.strip()]

        if not segments:
            return PropertyUrlClassification("unknown_non_property", False, "homepage/root domain")
        if normalized_root and hostname and hostname != normalized_root and not hostname.endswith(f".{normalized_root}"):
            return PropertyUrlClassification("unknown_non_property", False, "outside source root domain")

        first = segments[0]
        joined = "/".join(segments)

        if first in CONTACT_SEGMENTS:
            return PropertyUrlClassification("contact_page", False, f"excluded path: /{first}")
        if first in LEGAL_SEGMENTS:
            return PropertyUrlClassification("legal_page", False, f"excluded path: /{first}")
        if first in BLOG_SEGMENTS:
            return PropertyUrlClassification("blog_news", False, f"excluded path: /{first}")
        if first in OFFICE_SEGMENTS:
            return PropertyUrlClassification("office_page", False, f"excluded path: /{first}")
        if any(segment in SERVICE_SEGMENTS for segment in segments):
            return PropertyUrlClassification("service_page", False, f"excluded path: /{joined}")
        if any(segment in COMMERCIAL_SEGMENTS for segment in segments):
            return PropertyUrlClassification("commercial_page", False, f"commercial path: /{joined}")
        if first in EXACT_INDEX_PATHS and len(segments) == 1:
            return PropertyUrlClassification("listing_index", False, f"listing index: /{first}")

        if self._is_ogonline_detail_path(segments):
            return PropertyUrlClassification("property_detail_candidate", True, "")
        if first in DETAIL_PREFIXES and len(segments) >= 2 and self._has_property_slug(segments[1:]):
            return PropertyUrlClassification("property_detail_candidate", True, "")
        if self._has_property_slug(segments):
            return PropertyUrlClassification("property_detail_candidate", True, "")

        if first in EXACT_INDEX_PATHS:
            return PropertyUrlClassification("listing_index", False, f"listing-like path without property slug: /{joined}")
        return PropertyUrlClassification("unknown_non_property", False, f"unclassified non-property path: /{joined}")

    def _has_property_slug(self, segments: list[str]) -> bool:
        for segment in segments:
            if segment in SERVICE_SEGMENTS or segment in BLOG_SEGMENTS or segment in LEGAL_SEGMENTS:
                return False
            if _ADDRESS_SLUG_PATTERN.fullmatch(segment):
                return True
            if ADDRESS_OR_ID_PATTERN.search(segment):
                return True
        return False

    def _is_ogonline_detail_path(self, segments: list[str]) -> bool:
        if len(segments) < 5:
            return False
        if segments[0] != "aanbod" or segments[1] != "wonen":
            return False
        if not _OGONLINE_DETAIL_ID_PATTERN.fullmatch(segments[-1]):
            return False
        slug = segments[-2]
        return "-" in slug and any(character.isdigit() for character in slug)
