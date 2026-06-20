from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from selectolax.parser import HTMLParser

from domek_wonen.compliance import robots_gate
from domek_wonen.runtime_settings import load_runtime_settings


DISCOVERABLE_STRATEGIES = {"listing_html", "sitemap_with_listings", "wp_json"}
SITEMAP_PATHS = (
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
    "/wp-sitemap.xml",
    "/sitemap/sitemap-index.xml",
)
LISTING_HINTS = ("listing", "listings", "woning", "woningen", "aanbod", "huis", "huizen", "koop", "te-koop", "object", "appartement")
PRICE_PATTERN = r"(?:EUR|€)\s?[\d\.\,]+(?:\s*[-,/]?\s*(?:k\.k\.|p/m))?|prijs op aanvraag"
AREA_PATTERN = r"\d+\s?m(?:2|²)\b"
CITY_POSTCODE_PATTERN = re.compile(r"\b\d{4}\s?[A-Z]{2}\s+([A-Z][A-Za-z'().\- ]+)", flags=re.IGNORECASE)
CITY_LINE_PATTERN = re.compile(r"\b(?:plaats|city|woonplaats)\s*[:\-]?\s*([A-Z][A-Za-z'().\- ]+)", flags=re.IGNORECASE)
BLOCK_MARKERS = {
    403: "http_403",
    429: "http_429",
}
CHALLENGE_MARKERS = ("captcha", "g-recaptcha", "grecaptcha", "hcaptcha", "cf-turnstile", "checking your browser")


@dataclass(slots=True)
class MiniHarvestListing:
    source_url: str
    title: str = ""
    price: str = ""
    city: str = ""
    area: str = ""
    address: str = ""


@dataclass(slots=True)
class MiniHarvestResult:
    domain: str
    strategy: str
    listings_found: int
    listings_parsed: int
    fill_rate_price: float
    fill_rate_city: float
    fill_rate_area: float
    fill_rate_url: float
    sample_listings: list[dict[str, str]] = field(default_factory=list)
    blocker_reason: str | None = None
    harvest_ok: bool = False


@dataclass(slots=True)
class MiniHarvestRunSummary:
    run_id: str
    generated_at: str
    domains_total: int
    domains_harvest_ok: int
    domains_blocked: int
    total_properties_extracted: int
    mean_fill_rate_price: float
    mean_fill_rate_city: float
    mean_fill_rate_area: float
    mean_fill_rate_url: float
    verdict: str


@dataclass(slots=True)
class _FetchedResponse:
    url: str
    status_code: int
    text: str
    headers: dict[str, str]


def _collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _normalize_text(value: str) -> str:
    return _collapse_whitespace(unescape(value or ""))


def _build_url(domain: str, path: str) -> str:
    normalized_path = path if path.startswith("/") else f"/{path}"
    return urlunsplit(("https", domain, normalized_path, "", ""))


def _path_with_query(url: str) -> str:
    parsed = urlsplit(url)
    return f"{parsed.path or '/'}{f'?{parsed.query}' if parsed.query else ''}"


def _normalize_response(response: object, url: str) -> _FetchedResponse:
    if isinstance(response, _FetchedResponse):
        return response
    if isinstance(response, httpx.Response):
        return _FetchedResponse(
            url=str(response.url),
            status_code=response.status_code,
            text=response.text,
            headers={str(key).lower(): str(value) for key, value in response.headers.items()},
        )
    status_code = int(getattr(response, "status_code", getattr(response, "status", 200)))
    text = getattr(response, "text", "")
    raw_headers = getattr(response, "headers", {}) or {}
    return _FetchedResponse(
        url=url,
        status_code=status_code,
        text=text,
        headers={str(key).lower(): str(value) for key, value in raw_headers.items()},
    )


def _default_fetcher(url: str, headers: dict[str, str], timeout: float) -> _FetchedResponse:
    response = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
    return _normalize_response(response, url)


def _blocked_reason(response: _FetchedResponse | None) -> str | None:
    if response is None:
        return None
    if response.status_code in BLOCK_MARKERS:
        return BLOCK_MARKERS[response.status_code]
    haystack = " ".join(
        (
            response.text.lower(),
            response.headers.get("location", "").lower(),
            response.headers.get("server", "").lower(),
        )
    )
    if any(marker in haystack for marker in CHALLENGE_MARKERS):
        return "captcha"
    if "login" in haystack or "inloggen" in haystack or "sign in" in haystack:
        return "login_wall"
    return None


class _RequestManager:
    def __init__(
        self,
        domain: str,
        *,
        fetcher,
        timeout_seconds: float,
        user_agent: str,
        crawl_delay_seconds: float,
        sleep_between_requests: bool,
    ) -> None:
        self.domain = domain
        self.fetcher = fetcher
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent
        self.crawl_delay_seconds = crawl_delay_seconds
        self.sleep_between_requests = sleep_between_requests

    def fetch_url(self, url: str) -> _FetchedResponse | None:
        parsed = urlsplit(url)
        request_domain = (parsed.hostname or self.domain).lower()
        gate_path = _path_with_query(url)
        if not robots_gate.can_fetch(request_domain, gate_path):
            return None
        if self.sleep_between_requests and self.crawl_delay_seconds > 0:
            time.sleep(self.crawl_delay_seconds)
        response = self.fetcher(
            url,
            {"User-Agent": self.user_agent},
            self.timeout_seconds,
        )
        return _normalize_response(response, url)

    def fetch_path(self, path: str) -> _FetchedResponse | None:
        return self.fetch_url(_build_url(self.domain, path))


def _extract_sitemap_urls(text: str) -> list[str]:
    return re.findall(r"<loc>\s*(https?://[^<\s]+)\s*</loc>", text or "", flags=re.IGNORECASE)


def _extract_wp_rest_bases(types_payload: str) -> list[str]:
    try:
        payload = json.loads(types_payload)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, dict):
        return []
    rest_bases: list[str] = []
    for key, value in payload.items():
        if not isinstance(value, dict):
            continue
        haystack = " ".join(str(value.get(field, "")) for field in ("slug", "name", "description", "rest_base")).lower()
        if key.lower() in LISTING_HINTS or any(hint in haystack for hint in LISTING_HINTS):
            rest_base = str(value.get("rest_base") or key).strip("/")
            if rest_base and rest_base not in rest_bases:
                rest_bases.append(rest_base)
    return rest_bases


def _find_price(text: str) -> str:
    match = re.search(PRICE_PATTERN, text or "", flags=re.IGNORECASE)
    return _normalize_text(match.group(0)) if match else ""


def _find_area(text: str) -> str:
    match = re.search(AREA_PATTERN, text or "", flags=re.IGNORECASE)
    return _normalize_text(match.group(0)) if match else ""


def _find_city(text: str) -> str:
    postcode_match = CITY_POSTCODE_PATTERN.search(text or "")
    if postcode_match:
        return _normalize_text(postcode_match.group(1))
    city_match = CITY_LINE_PATTERN.search(text or "")
    if city_match:
        return _normalize_text(city_match.group(1))
    loose_match = re.search(
        r"(?:EUR|€)[^A-Z]*[A-Z]?[A-Za-z\.\,\s]*\b([A-Z][A-Za-z'().\-]+(?:\s+[A-Z][A-Za-z'().\-]+)*)\b\s+\d+\s?m(?:2|²)\b",
        text or "",
        flags=re.IGNORECASE,
    )
    return _normalize_text(loose_match.group(1)) if loose_match else ""


def _extract_meta_content(html: str, key: str) -> str:
    pattern = re.compile(
        rf"<meta[^>]+(?:property|name)=[\"']{re.escape(key)}[\"'][^>]+content=[\"'](?P<value>[^\"']+)[\"'][^>]*>",
        flags=re.IGNORECASE,
    )
    match = pattern.search(html or "")
    return _normalize_text(match.group("value")) if match else ""


def _extract_title(tree: HTMLParser, html: str) -> str:
    if tree.css_first("h1"):
        return _normalize_text(tree.css_first("h1").text(separator=" ", strip=True))
    title_match = re.search(r"<title[^>]*>(?P<body>.*?)</title>", html or "", flags=re.IGNORECASE | re.DOTALL)
    if title_match:
        return _normalize_text(re.sub(r"<[^>]+>", " ", title_match.group("body")))
    return ""


def _extract_detail_listing(html: str, source_url: str) -> MiniHarvestListing:
    tree = HTMLParser(html or "")
    visible_text = tree.body.text(separator=" ", strip=True) if tree.body else tree.text(separator=" ", strip=True)
    listing = MiniHarvestListing(
        source_url=source_url,
        title=_extract_title(tree, html),
        price=_find_price(visible_text),
        city=_find_city(visible_text),
        area=_find_area(visible_text),
        address="",
    )

    for script in tree.css('script[type="application/ld+json"]'):
        body = _collapse_whitespace(script.text())
        if not body:
            continue
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            continue
        records = payload if isinstance(payload, list) else [payload]
        for record in records:
            if not isinstance(record, dict):
                continue
            if not listing.title:
                listing.title = _normalize_text(str(record.get("name") or ""))
            address = record.get("address")
            if isinstance(address, dict):
                if not listing.city:
                    listing.city = _normalize_text(str(address.get("addressLocality") or ""))
                if not listing.address:
                    listing.address = _normalize_text(str(address.get("streetAddress") or ""))
            offers = record.get("offers")
            if isinstance(offers, dict) and not listing.price:
                amount = _normalize_text(str(offers.get("price") or ""))
                currency = _normalize_text(str(offers.get("priceCurrency") or ""))
                if amount:
                    listing.price = _collapse_whitespace(f"{currency} {amount}".strip())

    if not listing.title:
        listing.title = _extract_meta_content(html, "og:title")
    if not listing.price:
        listing.price = _extract_meta_content(html, "product:price:amount") or _extract_meta_content(html, "price")
    if not listing.city:
        listing.city = _find_city(_extract_meta_content(html, "og:description"))
    if not listing.area:
        listing.area = _find_area(_extract_meta_content(html, "og:description"))
    return listing


def _container_text(node) -> str:
    return _normalize_text(node.text(separator=" ", strip=True))


def _anchor_score(url: str, text: str) -> int:
    lowered_url = url.lower()
    lowered_text = text.lower()
    score = 0
    if any(hint in lowered_url for hint in LISTING_HINTS):
        score += 3
    if _find_price(text):
        score += 2
    if _find_area(text):
        score += 1
    if _find_city(text):
        score += 1
    if "verkocht" in lowered_text or "onder bod" in lowered_text or "te koop" in lowered_text:
        score += 1
    return score


def _extract_card_listings(html: str, *, base_url: str, domain: str, max_listings: int) -> list[MiniHarvestListing]:
    tree = HTMLParser(html or "")
    listings: list[MiniHarvestListing] = []
    seen_urls: set[str] = set()

    for anchor in tree.css("a[href]"):
        href = (anchor.attributes.get("href") or "").strip()
        if not href:
            continue
        resolved_url = urljoin(base_url, href)
        if (urlsplit(resolved_url).hostname or "").lower() != domain:
            continue

        container = anchor
        for _ in range(4):
            if container.parent is None:
                break
            container = container.parent
            if container.tag in {"article", "li", "div"}:
                break

        text = _container_text(container)
        if _anchor_score(resolved_url, text) < 4:
            continue
        if resolved_url in seen_urls:
            continue
        seen_urls.add(resolved_url)

        title = _normalize_text(anchor.text(separator=" ", strip=True))
        if not title:
            heading = container.css_first("h1, h2, h3, h4")
            title = _normalize_text(heading.text(separator=" ", strip=True)) if heading else ""
        listings.append(
            MiniHarvestListing(
                source_url=resolved_url,
                title=title,
                price=_find_price(text),
                city=_find_city(text),
                area=_find_area(text),
                address="",
            )
        )
        if len(listings) >= max_listings:
            break
    return listings


def _listing_url_matches(url: str, listing_pattern: str | None, domain: str) -> bool:
    parsed = urlsplit(url)
    if (parsed.hostname or "").lower() != domain:
        return False
    if listing_pattern:
        return listing_pattern.lower() in parsed.path.lower()
    return any(hint in parsed.path.lower() for hint in LISTING_HINTS)


def _compute_fill_rate(listings: list[MiniHarvestListing], attr: str) -> float:
    if not listings:
        return 0.0
    non_empty = sum(1 for listing in listings if getattr(listing, attr))
    return non_empty / len(listings)


def summarize_result(domain: str, strategy: str, listings_found: int, listings: list[MiniHarvestListing], blocker_reason: str | None) -> MiniHarvestResult:
    parsed = listings
    fill_rate_price = _compute_fill_rate(parsed, "price")
    fill_rate_city = _compute_fill_rate(parsed, "city")
    fill_rate_area = _compute_fill_rate(parsed, "area")
    fill_rate_url = _compute_fill_rate(parsed, "source_url")
    return MiniHarvestResult(
        domain=domain,
        strategy=strategy,
        listings_found=listings_found,
        listings_parsed=len(parsed),
        fill_rate_price=fill_rate_price,
        fill_rate_city=fill_rate_city,
        fill_rate_area=fill_rate_area,
        fill_rate_url=fill_rate_url,
        sample_listings=[asdict(listing) for listing in parsed[:3]],
        blocker_reason=blocker_reason,
        harvest_ok=len(parsed) > 0 and blocker_reason is None,
    )


def harvest_domain_sample(
    domain: str,
    strategy: str,
    aanbod_url: str | None = None,
    listing_pattern: str | None = None,
    fetcher=None,
    max_listings: int = 10,
    max_detail_pages: int = 5,
) -> MiniHarvestResult:
    normalized_domain = domain.strip().lower()
    if strategy not in DISCOVERABLE_STRATEGIES:
        return summarize_result(normalized_domain, strategy, 0, [], "unsupported_strategy")

    settings = load_runtime_settings(load_dotenv_file=False)
    request_manager = _RequestManager(
        normalized_domain,
        fetcher=fetcher or _default_fetcher,
        timeout_seconds=float(settings.request_timeout_seconds),
        user_agent=settings.user_agent,
        crawl_delay_seconds=robots_gate.crawl_delay(normalized_domain),
        sleep_between_requests=fetcher is None,
    )
    blocker_reason: str | None = None

    if strategy == "listing_html":
        candidate_url = aanbod_url or _build_url(normalized_domain, listing_pattern or "/")
        response = request_manager.fetch_url(candidate_url)
        blocker_reason = _blocked_reason(response)
        if response is None or response.status_code != 200 or blocker_reason is not None:
            return summarize_result(normalized_domain, strategy, 0, [], blocker_reason or "fetch_failed")
        listings = _extract_card_listings(response.text, base_url=response.url, domain=normalized_domain, max_listings=max_listings)
        return summarize_result(normalized_domain, strategy, len(listings), listings, None)

    if strategy == "sitemap_with_listings":
        listing_urls: list[str] = []
        for sitemap_path in SITEMAP_PATHS:
            response = request_manager.fetch_path(sitemap_path)
            blocker_reason = _blocked_reason(response)
            if response is None or blocker_reason is not None:
                if blocker_reason is not None:
                    return summarize_result(normalized_domain, strategy, len(listing_urls), [], blocker_reason)
                continue
            if response.status_code != 200:
                continue
            locs = _extract_sitemap_urls(response.text)
            nested_sitemaps = [loc for loc in locs if loc.lower().endswith(".xml")]
            listing_urls.extend([loc for loc in locs if _listing_url_matches(loc, listing_pattern, normalized_domain)])
            if listing_urls:
                break
            for nested in nested_sitemaps[:2]:
                nested_response = request_manager.fetch_url(nested)
                blocker_reason = _blocked_reason(nested_response)
                if nested_response is None or blocker_reason is not None:
                    if blocker_reason is not None:
                        return summarize_result(normalized_domain, strategy, len(listing_urls), [], blocker_reason)
                    continue
                if nested_response.status_code != 200:
                    continue
                nested_urls = _extract_sitemap_urls(nested_response.text)
                listing_urls.extend([loc for loc in nested_urls if _listing_url_matches(loc, listing_pattern, normalized_domain)])
                if listing_urls:
                    break
            if listing_urls:
                break
        listing_urls = list(dict.fromkeys(listing_urls))[:max_listings]
        parsed: list[MiniHarvestListing] = []
        for listing_url in listing_urls[:max_detail_pages]:
            detail_response = request_manager.fetch_url(listing_url)
            blocker_reason = _blocked_reason(detail_response)
            if detail_response is None:
                continue
            if blocker_reason is not None:
                return summarize_result(normalized_domain, strategy, len(listing_urls), parsed, blocker_reason)
            if detail_response.status_code != 200:
                continue
            parsed.append(_extract_detail_listing(detail_response.text, detail_response.url))
        return summarize_result(normalized_domain, strategy, len(listing_urls), parsed, None if parsed else blocker_reason)

    types_response = request_manager.fetch_path("/wp-json/wp/v2/types")
    blocker_reason = _blocked_reason(types_response)
    if types_response is None or blocker_reason is not None or types_response.status_code != 200:
        return summarize_result(normalized_domain, strategy, 0, [], blocker_reason or "fetch_failed")

    parsed: list[MiniHarvestListing] = []
    listings_found = 0
    for rest_base in _extract_wp_rest_bases(types_response.text):
        collection_response = request_manager.fetch_path(f"/wp-json/wp/v2/{rest_base}?per_page={max_listings}")
        blocker_reason = _blocked_reason(collection_response)
        if collection_response is None or blocker_reason is not None or collection_response.status_code != 200:
            if blocker_reason is not None:
                return summarize_result(normalized_domain, strategy, listings_found, parsed, blocker_reason)
            continue
        try:
            payload = json.loads(collection_response.text)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, list):
            continue
        listings_found = max(listings_found, len(payload))
        for item in payload[:max_listings]:
            if not isinstance(item, dict):
                continue
            rendered_title = item.get("title", {})
            title = ""
            if isinstance(rendered_title, dict):
                title = _normalize_text(str(rendered_title.get("rendered") or ""))
            source_url = _normalize_text(str(item.get("link") or ""))
            excerpt = item.get("excerpt", {})
            excerpt_text = _normalize_text(str(excerpt.get("rendered") or "")) if isinstance(excerpt, dict) else ""
            content = item.get("content", {})
            content_text = _normalize_text(str(content.get("rendered") or "")) if isinstance(content, dict) else ""
            merged_text = " ".join(part for part in (title, excerpt_text, content_text) if part)
            listing = MiniHarvestListing(
                source_url=source_url,
                title=title,
                price=_find_price(merged_text),
                city=_find_city(merged_text),
                area=_find_area(merged_text),
                address="",
            )
            if source_url and (not listing.price or not listing.city or not listing.area) and len(parsed) < max_detail_pages:
                detail_response = request_manager.fetch_url(source_url)
                detail_blocker = _blocked_reason(detail_response)
                if detail_response is not None and detail_blocker is None and detail_response.status_code == 200:
                    listing = _extract_detail_listing(detail_response.text, detail_response.url)
                elif detail_blocker is not None:
                    blocker_reason = detail_blocker
                    return summarize_result(normalized_domain, strategy, listings_found, parsed, blocker_reason)
            parsed.append(listing)
        if parsed:
            break
    return summarize_result(normalized_domain, strategy, listings_found, parsed[:max_listings], None if parsed else blocker_reason)


def verdict_from_results(results: list[MiniHarvestResult]) -> str:
    harvest_ok = [result for result in results if result.harvest_ok]
    if not harvest_ok:
        return "POBRE"
    price_mean = sum(result.fill_rate_price for result in harvest_ok) / len(harvest_ok)
    city_mean = sum(result.fill_rate_city for result in harvest_ok) / len(harvest_ok)
    if len(harvest_ok) >= 10 and price_mean >= 0.7 and city_mean >= 0.7:
        return "COSECHABLE"
    if price_mean >= 0.4 and city_mean >= 0.4:
        return "PARCIAL"
    return "POBRE"


def summarize_run(results: list[MiniHarvestResult], *, run_id: str, generated_at: str) -> MiniHarvestRunSummary:
    harvest_ok = [result for result in results if result.harvest_ok]
    blocked = [result for result in results if result.blocker_reason]
    total_properties = sum(result.listings_parsed for result in harvest_ok)
    return MiniHarvestRunSummary(
        run_id=run_id,
        generated_at=generated_at,
        domains_total=len(results),
        domains_harvest_ok=len(harvest_ok),
        domains_blocked=len(blocked),
        total_properties_extracted=total_properties,
        mean_fill_rate_price=(sum(result.fill_rate_price for result in harvest_ok) / len(harvest_ok)) if harvest_ok else 0.0,
        mean_fill_rate_city=(sum(result.fill_rate_city for result in harvest_ok) / len(harvest_ok)) if harvest_ok else 0.0,
        mean_fill_rate_area=(sum(result.fill_rate_area for result in harvest_ok) / len(harvest_ok)) if harvest_ok else 0.0,
        mean_fill_rate_url=(sum(result.fill_rate_url for result in harvest_ok) / len(harvest_ok)) if harvest_ok else 0.0,
        verdict=verdict_from_results(results),
    )


def format_rate(value: float) -> str:
    return f"{value * 100:.1f}%"


def generate_markdown_report(summary: MiniHarvestRunSummary, results: list[MiniHarvestResult]) -> str:
    lines = [
        "# Mini Harvest Report",
        "",
        f"- run_id: {summary.run_id}",
        f"- generated_at: {summary.generated_at}",
        f"- domains_total: {summary.domains_total}",
        f"- domains_harvest_ok: {summary.domains_harvest_ok}",
        f"- domains_blocked: {summary.domains_blocked}",
        f"- total_properties_extracted: {summary.total_properties_extracted}",
        f"- mean_fill_rate_price: {format_rate(summary.mean_fill_rate_price)}",
        f"- mean_fill_rate_city: {format_rate(summary.mean_fill_rate_city)}",
        f"- mean_fill_rate_area: {format_rate(summary.mean_fill_rate_area)}",
        f"- mean_fill_rate_url: {format_rate(summary.mean_fill_rate_url)}",
        f"- verdict: {summary.verdict}",
        "",
        "## Domain Table",
    ]
    for result in results:
        lines.append(
            f"- {result.domain}: strategy={result.strategy}, found={result.listings_found}, parsed={result.listings_parsed}, "
            f"price={format_rate(result.fill_rate_price)}, city={format_rate(result.fill_rate_city)}, "
            f"area={format_rate(result.fill_rate_area)}, url={format_rate(result.fill_rate_url)}, "
            f"blocker={result.blocker_reason or '-'}"
        )
    return "\n".join(lines) + "\n"


def write_run_outputs(
    output_dir: Path,
    *,
    report_text: str,
    results: list[MiniHarvestResult],
) -> dict[str, Path]:
    import csv

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "mini_harvest_report.md"
    inventory_path = output_dir / "mini_harvest_inventory.csv"
    samples_path = output_dir / "mini_harvest_samples.csv"
    report_path.write_text(report_text, encoding="utf-8")

    with inventory_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "domain",
                "strategy",
                "listings_found",
                "listings_parsed",
                "fill_rate_price",
                "fill_rate_city",
                "fill_rate_area",
                "fill_rate_url",
                "blocker_reason",
                "harvest_ok",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "domain": result.domain,
                    "strategy": result.strategy,
                    "listings_found": result.listings_found,
                    "listings_parsed": result.listings_parsed,
                    "fill_rate_price": f"{result.fill_rate_price:.4f}",
                    "fill_rate_city": f"{result.fill_rate_city:.4f}",
                    "fill_rate_area": f"{result.fill_rate_area:.4f}",
                    "fill_rate_url": f"{result.fill_rate_url:.4f}",
                    "blocker_reason": result.blocker_reason or "",
                    "harvest_ok": str(result.harvest_ok).lower(),
                }
            )

    with samples_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["domain", "strategy", "source_url", "title", "price", "city", "area", "address"],
        )
        writer.writeheader()
        for result in results:
            for listing in result.sample_listings:
                writer.writerow(
                    {
                        "domain": result.domain,
                        "strategy": result.strategy,
                        **{key: listing.get(key, "") for key in ("source_url", "title", "price", "city", "area", "address")},
                    }
                )

    return {
        "report_md": report_path,
        "inventory_csv": inventory_path,
        "samples_csv": samples_path,
    }
