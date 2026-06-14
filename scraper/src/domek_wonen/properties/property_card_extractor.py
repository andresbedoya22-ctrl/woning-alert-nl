from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from .models import PropertyCandidate, PropertySource
from .property_dedupe import normalize_property_url

LISTING_HINTS = (
    "woning",
    "woningen",
    "aanbod",
    "object",
    "huis",
    "huizen",
    "appartement",
    "koop",
    "te-koop",
    "panden",
    "detail",
)
EXCLUDED_HINTS = (
    "contact",
    "privacy",
    "cookie",
    "over-ons",
    "taxatie",
    "hypotheek",
    "blog",
    "nieuws",
    "vacature",
    "reviews",
    "voorwaarden",
    "disclaimer",
)
STATUS_PATTERNS = (
    "verkocht onder voorbehoud",
    "verkocht o.v.",
    "onder bod",
    "verkocht",
    "beschikbaar",
    "te koop",
)
PRICE_PATTERN = r"€\s?[\d\.\,]+(?:\s*[a-z.]+)?"
LIVING_AREA_PATTERN = r"\d+\s?m²\s*(?:woonoppervlakte|wonen|living)?"
PLOT_AREA_PATTERN = r"\d+\s?m²\s*(?:perceel|plot|kavel)"
ROOMS_PATTERN = r"\d+\s*(?:kamers?|rooms?)"


@dataclass(slots=True)
class HtmlNode:
    tag: str
    attrs: dict[str, str]
    parent: "HtmlNode | None" = None
    children: list["HtmlNode"] = field(default_factory=list)
    chunks: list[str] = field(default_factory=list)

    def add_child(self, child: "HtmlNode") -> None:
        self.children.append(child)

    def add_text(self, text: str) -> None:
        if text.strip():
            self.chunks.append(text)

    def text_content(self) -> str:
        parts = list(self.chunks)
        for child in self.children:
            parts.append(child.text_content())
        return _collapse_whitespace(" ".join(parts))

    def iter_descendants(self) -> list["HtmlNode"]:
        nodes: list[HtmlNode] = []
        stack = [self]
        while stack:
            node = stack.pop()
            nodes.append(node)
            stack.extend(reversed(node.children))
        return nodes


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = HtmlNode(tag="document", attrs={})
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = HtmlNode(tag=tag.lower(), attrs={key: value or "" for key, value in attrs}, parent=self.stack[-1])
        self.stack[-1].add_child(node)
        self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        if len(self.stack) > 1:
            self.stack.pop()

    def handle_data(self, data: str) -> None:
        self.stack[-1].add_text(unescape(data))


def _collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _normalized_attr(node: HtmlNode, key: str) -> str:
    return (node.attrs.get(key) or "").strip().lower()


def _container_score(node: HtmlNode) -> int:
    class_blob = " ".join(
        value for value in (_normalized_attr(node, "class"), _normalized_attr(node, "id")) if value
    )
    score = 0
    if node.tag in {"article", "li"}:
        score += 2
    if any(token in class_blob for token in ("card", "listing", "object", "woning", "aanbod", "result")):
        score += 3
    return score


def _find_line(text: str, pattern: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return _collapse_whitespace(match.group(0)) if match else ""


def _extract_address(text: str) -> tuple[str, str]:
    address_match = re.search(
        r"([A-ZÀ-ÿ][A-Za-zÀ-ÿ'()./\- ]+\d+[A-Za-z0-9/\-]*)(?:,\s*|\s+)(\d{4}\s?[A-Z]{2}\s+[A-ZÀ-ÿ][A-Za-zÀ-ÿ'().\- ]+)",
        text,
        flags=re.IGNORECASE,
    )
    if address_match:
        return (_collapse_whitespace(address_match.group(1)), _collapse_whitespace(address_match.group(2)))

    city_match = re.search(r"\b\d{4}\s?[A-Z]{2}\s+([A-ZÀ-ÿ][A-Za-zÀ-ÿ'().\- ]+)", text, flags=re.IGNORECASE)
    return ("", _collapse_whitespace(city_match.group(1)) if city_match else "")


def _extract_status(text: str) -> str:
    lowered = text.lower()
    for pattern in STATUS_PATTERNS:
        if pattern in lowered:
            return pattern
    return ""


def _extract_image_url(container: HtmlNode, base_url: str) -> str:
    for node in container.iter_descendants():
        if node.tag != "img":
            continue
        src = (node.attrs.get("src") or node.attrs.get("data-src") or "").strip()
        if src:
            return urljoin(base_url, src)
    return ""


def _container_signal_score(node: HtmlNode) -> int:
    text = node.text_content()
    score = _container_score(node)
    address_raw, city_raw = _extract_address(text)
    if _find_line(text, PRICE_PATTERN):
        score += 4
    if _extract_status(text):
        score += 2
    if _find_line(text, LIVING_AREA_PATTERN):
        score += 2
    if _find_line(text, ROOMS_PATTERN):
        score += 2
    if address_raw or city_raw:
        score += 3
    if any(desc.tag == "img" for desc in node.iter_descendants()):
        score += 1
    return score


def _best_container(anchor: HtmlNode) -> HtmlNode:
    best = anchor
    depth = 0
    current = anchor
    while current.parent is not None and depth < 5:
        current = current.parent
        depth += 1
        if _container_signal_score(current) > _container_signal_score(best):
            best = current
    return best


def _same_domain(candidate_url: str, root_domain: str) -> bool:
    if not root_domain:
        return True
    hostname = (urlparse(candidate_url).hostname or "").lower()
    return hostname == root_domain or hostname.endswith("." + root_domain)


def _looks_like_property_link(url: str, text: str) -> bool:
    lowered_url = url.lower()
    lowered_text = text.lower()
    if any(token in lowered_url for token in EXCLUDED_HINTS):
        return False
    score = 0
    if any(token in lowered_url for token in LISTING_HINTS):
        score += 2
    if any(token in lowered_text for token in ("€", "m²", "kamer", "slaapkamer", "te koop", "onder bod", "verkocht")):
        score += 2
    if re.search(r"\b\d{4}\s?[a-z]{2}\b", lowered_text, flags=re.IGNORECASE):
        score += 1
    return score >= 2


def _anchor_score(anchor: HtmlNode, container: HtmlNode, resolved_url: str) -> int:
    score = 0
    href = (anchor.attrs.get("href") or "").strip().lower()
    anchor_text = anchor.text_content().lower()
    container_text = container.text_content()
    if _looks_like_property_link(resolved_url, container_text):
        score += 3
    if any(token in href for token in LISTING_HINTS):
        score += 2
    if anchor_text and anchor_text not in {"bekijk", "lees meer", "meer info", "details"}:
        score += 1
    address_raw, city_raw = _extract_address(container_text)
    if address_raw or city_raw:
        score += 2
    if _find_line(container_text, PRICE_PATTERN):
        score += 2
    return score


def _extract_title(container: HtmlNode, anchor: HtmlNode) -> str:
    for node in container.iter_descendants():
        if node.tag in {"h1", "h2", "h3", "h4"}:
            text = node.text_content()
            if text:
                return text
    return anchor.text_content()


def _confidence_from_fields(candidate: PropertyCandidate) -> float:
    score = 0.25
    if candidate.title:
        score += 0.1
    if candidate.address_raw or candidate.city_raw:
        score += 0.2
    if candidate.price_raw:
        score += 0.15
    if candidate.status_raw:
        score += 0.1
    if candidate.living_area_raw or candidate.rooms_raw or candidate.plot_area_raw:
        score += 0.1
    if candidate.image_url:
        score += 0.05
    if candidate.property_url:
        score += 0.05
    return min(score, 0.95)


class PropertyCardExtractor:
    def extract(self, html: str, source: PropertySource, source_url: str | None = None) -> list[PropertyCandidate]:
        builder = _TreeBuilder()
        builder.feed(html or "")
        base_url = source_url or source.aanbod_url or source.website
        extracted: list[PropertyCandidate] = []
        seen_urls: set[str] = set()
        seen_containers: set[int] = set()

        for node in builder.root.iter_descendants():
            if node.tag != "a":
                continue
            container = _best_container(node)
            container_key = id(container)
            if container_key in seen_containers:
                continue
            seen_containers.add(container_key)

            if _container_signal_score(container) < 6:
                continue

            anchor_candidates: list[tuple[int, HtmlNode, str]] = []
            for anchor in container.iter_descendants():
                if anchor.tag != "a":
                    continue
                href = (anchor.attrs.get("href") or "").strip()
                if not href:
                    continue
                resolved_url = urljoin(base_url, href)
                if urlparse(resolved_url).scheme not in {"http", "https"}:
                    continue
                if not _same_domain(resolved_url, source.root_domain):
                    continue
                anchor_candidates.append((_anchor_score(anchor, container, resolved_url), anchor, resolved_url))

            if not anchor_candidates:
                continue

            anchor_candidates.sort(key=lambda item: item[0], reverse=True)
            best_score, best_anchor, resolved_url = anchor_candidates[0]
            container_text = container.text_content()
            if best_score < 5:
                continue
            if not _looks_like_property_link(resolved_url, container_text):
                continue

            normalized_url = normalize_property_url(resolved_url)
            if normalized_url in seen_urls:
                continue
            seen_urls.add(normalized_url)

            title = _extract_title(container, best_anchor)
            address_raw, city_raw = _extract_address(container_text)
            price_raw = _find_line(container_text, PRICE_PATTERN)
            status_raw = _extract_status(container_text)
            living_area_raw = _find_line(container_text, LIVING_AREA_PATTERN)
            plot_area_raw = _find_line(container_text, PLOT_AREA_PATTERN)
            rooms_raw = _find_line(container_text, ROOMS_PATTERN)
            image_url = _extract_image_url(container, base_url)

            candidate = PropertyCandidate(
                source_id=source.source_id,
                source_url=source.aanbod_url,
                root_domain=source.root_domain,
                gemeente=source.gemeente,
                property_url=resolved_url,
                candidate_type="property_card_anchor",
                link_text=best_anchor.text_content(),
                extraction_method="container_card_best_anchor",
                is_property_like=True,
                title=title,
                address_raw=address_raw,
                city_raw=city_raw,
                price_raw=price_raw,
                status_raw=status_raw,
                living_area_raw=living_area_raw,
                plot_area_raw=plot_area_raw,
                rooms_raw=rooms_raw,
                image_url=image_url,
            )
            candidate.extraction_confidence = _confidence_from_fields(candidate)
            if not candidate.address_raw and not candidate.price_raw:
                candidate.needs_review = True
                candidate.review_reason = "missing address and price signals"
            extracted.append(candidate)
        return extracted
