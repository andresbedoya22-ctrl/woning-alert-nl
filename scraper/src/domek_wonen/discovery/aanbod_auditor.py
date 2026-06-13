from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from time import perf_counter
from typing import Iterable
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

from .config import COMMON_AANBOD_PATHS, PAGE_LISTING_SIGNALS
from .models import AanbodAuditAttempt, SourceCandidate

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:  # pragma: no cover
    PlaywrightError = RuntimeError
    PlaywrightTimeoutError = TimeoutError
    sync_playwright = None

PRIORITY_TOKENS = (
    "aanbod",
    "woningaanbod",
    "koopwoningen",
    "koop",
    "te koop",
    "woningen",
    "huizen",
    "objecten",
)

RESIDENTIAL_SIGNALS = (
    "woning",
    "woningen",
    "appartement",
    "huis",
    "huizen",
    "woonhuis",
    "vrijstaand",
    "tussenwoning",
    "hoekwoning",
    "slaapkamers",
    "woonoppervlakte",
    "te koop",
    "k.k.",
    "vraagprijs",
)

COMMERCIAL_SIGNALS = (
    "bedrijfsaanbod",
    "bedrijfshuisvesting",
    "bedrijfsruimte",
    "kantoorruimte",
    "winkelruimte",
    "bedrijfsunit",
    "bedrijventerrein",
    "commercieel",
    "horeca",
    "belegging",
    "commercieel vastgoed",
    "vastgoedbelegging",
)
COMMERCIAL_HARD_BLOCK_TOKENS = (
    "bedrijfsaanbod",
    "bedrijfshuisvesting",
    "bedrijfsruimte",
    "kantoorruimte",
    "winkelruimte",
    "bedrijfsunit",
    "bedrijventerrein",
    "commercieel",
    "horeca",
    "belegging",
    "vastgoedbelegging",
)

PROJECT_SIGNALS = ("nieuwbouwproject", "project", "fase", "inschrijven", "woningtype")
DETAIL_SIGNALS = ("adres", "beschrijving", "kenmerken", "foto's", "plattegrond")
REJECTED_TOKENS = ("sitemap", "robots.txt", "contact", "taxatie", "waardebepaling", "blog", "team", "funda")
REJECTED_EXTENSIONS = (".xml", ".pdf")
HTML_CONTENT_MARKERS = ("text/html", "application/xhtml+xml")


@dataclass(slots=True)
class _LinkCandidate:
    url: str
    text: str


@dataclass(slots=True)
class _PageData:
    url: str
    status: int
    content_type: str
    html: str


@dataclass(slots=True)
class _PageAssessment:
    page_type: str
    confidence: int
    listing_signals: list[str]
    residential_signals: list[str]
    commercial_signals: list[str]
    quality_reason: str
    final_status: str
    rejection_reason: str
    commercial_hard_block: bool
    commercial_block_reason: str


class _HomepageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.first_h1 = ""
        self.visible_text: list[str] = []
        self.links: list[_LinkCandidate] = []
        self._capture_title = False
        self._capture_h1 = False
        self._ignore_depth = 0
        self._current_link_href = ""
        self._current_link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lower_tag = tag.lower()
        if lower_tag in {"script", "style", "noscript"}:
            self._ignore_depth += 1
            return
        if lower_tag == "title":
            self._capture_title = True
        elif lower_tag == "h1" and not self.first_h1:
            self._capture_h1 = True
        elif lower_tag == "a":
            href = ""
            for key, value in attrs:
                if key.lower() == "href" and value:
                    href = value.strip()
                    break
            self._current_link_href = href
            self._current_link_text = []

    def handle_endtag(self, tag: str) -> None:
        lower_tag = tag.lower()
        if lower_tag in {"script", "style", "noscript"} and self._ignore_depth > 0:
            self._ignore_depth -= 1
            return
        if lower_tag == "title":
            self._capture_title = False
        elif lower_tag == "h1":
            self._capture_h1 = False
        elif lower_tag == "a":
            text = " ".join("".join(self._current_link_text).split())
            if self._current_link_href:
                self.links.append(_LinkCandidate(url=self._current_link_href, text=text))
            self._current_link_href = ""
            self._current_link_text = []

    def handle_data(self, data: str) -> None:
        if self._ignore_depth > 0:
            return
        normalized = " ".join(data.split())
        if not normalized:
            return
        self.visible_text.append(normalized)
        if self._capture_title and not self.title:
            self.title = normalized
        if self._capture_h1 and not self.first_h1:
            self.first_h1 = normalized
        if self._current_link_href:
            self._current_link_text.append(normalized)


def _normalize_url(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    return raw.rstrip("/")


def _normalize_text(value: str) -> str:
    return " ".join((value or "").lower().split())


def _url_haystack(url: str) -> str:
    parsed = urlsplit(url)
    return f"{parsed.netloc}{parsed.path}".lower()


def _count_token_matches(text: str, tokens: Iterable[str]) -> list[str]:
    haystack = _normalize_text(text)
    return [token for token in tokens if token in haystack]


def _reject_reason(url: str) -> str:
    lowered = _url_haystack(url)
    if any(lowered.endswith(ext) for ext in REJECTED_EXTENSIONS):
        return "non_html_asset"
    for token in REJECTED_TOKENS:
        if token in lowered:
            return f"rejected_token:{token}"
    return ""


def _is_html_page(content_type: str, url: str) -> bool:
    lowered_content_type = (content_type or "").lower()
    if any(marker in lowered_content_type for marker in HTML_CONTENT_MARKERS):
        return True
    return not _reject_reason(url)


def _parse_page(html: str) -> tuple[str, str, str, list[_LinkCandidate]]:
    parser = _HomepageParser()
    try:
        parser.feed(html or "")
    except Exception:
        pass
    return parser.title, parser.first_h1, " ".join(parser.visible_text), parser.links


def _extract_internal_links(base_url: str, raw_links: list[_LinkCandidate]) -> list[_LinkCandidate]:
    base = urlsplit(base_url)
    seen: set[str] = set()
    results: list[_LinkCandidate] = []
    for link in raw_links:
        absolute = urljoin(f"{base_url.rstrip('/')}/", link.url.strip())
        parsed = urlsplit(absolute)
        if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != base.netloc.lower():
            continue
        normalized = absolute.split("#", 1)[0].rstrip("/")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        results.append(_LinkCandidate(url=normalized, text=link.text))
    return results


def _rank_link_candidate(link: _LinkCandidate) -> tuple[int, int]:
    text_matches = _count_token_matches(link.text, PRIORITY_TOKENS)
    url_matches = _count_token_matches(_url_haystack(link.url), PRIORITY_TOKENS)
    return len(text_matches) * 30 + len(url_matches) * 20, -len(link.url)


def _candidate_urls_from_homepage(homepage_url: str, html: str) -> list[str]:
    _, _, _, raw_links = _parse_page(html)
    ranked = sorted(
        (
            link
            for link in _extract_internal_links(homepage_url, raw_links)
            if _rank_link_candidate(link)[0] > 0 and not _reject_reason(link.url)
        ),
        key=_rank_link_candidate,
        reverse=True,
    )
    return [link.url for link in ranked]


def _candidate_urls_from_sitemap(xml_text: str) -> list[str]:
    if not (xml_text or "").strip():
        return []
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return []
    urls: list[str] = []
    seen: set[str] = set()
    for element in root.iter():
        tag = element.tag.lower()
        if not tag.endswith("loc") or not element.text:
            continue
        value = element.text.strip().rstrip("/")
        if not value or value in seen or _reject_reason(value):
            continue
        if _rank_link_candidate(_LinkCandidate(url=value, text=""))[0] <= 0:
            continue
        seen.add(value)
        urls.append(value)
    return urls


def _common_path_candidates(website: str) -> list[str]:
    root = _normalize_url(website)
    if not root:
        return []
    allowed_paths = (
        "/aanbod",
        "/woningaanbod",
        "/koopwoningen",
        "/huizen-te-koop",
        "/woningen-te-koop",
        "/koopaanbod",
        "/aanbod/koopwoningen",
    )
    configured = [path for path in COMMON_AANBOD_PATHS if path in allowed_paths]
    return [urljoin(f"{root}/", path.lstrip("/")) for path in configured]


def _fetch_page(page, url: str) -> _PageData:
    response = page.goto(url, wait_until="domcontentloaded", timeout=15000)
    html = page.content() or ""
    final_url = getattr(page, "url", url).rstrip("/")
    status = 0
    content_type = ""
    if response is not None:
        status = response.status
        content_type = (response.headers or {}).get("content-type", "")
        final_url = str(getattr(response, "url", final_url)).rstrip("/")
    return _PageData(url=final_url or url.rstrip("/"), status=status, content_type=content_type, html=html)


def _classify_page_type(url: str, text: str, residential_signals: list[str], commercial_signals: list[str]) -> tuple[str, str]:
    haystack = _normalize_text(text)
    path = _url_haystack(url)
    segments = [segment for segment in urlsplit(url).path.strip("/").split("/") if segment]
    if "bedrijfshuisvesting" in path or (commercial_signals and len(commercial_signals) >= max(2, len(residential_signals) + 1)):
        return "commercial_listing", "commercial_only"
    if any(token in haystack for token in PROJECT_SIGNALS) or "nieuwbouw" in path or "project" in path:
        return "project_page", "project_page"
    if len(segments) >= 3 and segments[0] == "aanbod":
        return "property_detail", "property_detail"
    if any(token in haystack for token in DETAIL_SIGNALS) and len(residential_signals) <= 5:
        return "property_detail", "property_detail"
    if len(residential_signals) >= 4 and ("aanbod" in path or "koopwoningen" in path or "woningaanbod" in path):
        return "listing_index", "listing_index"
    return "unknown", "unknown_page_type"


def _commercial_hard_block_reason(url: str, title: str, h1: str) -> str:
    url_text = _url_haystack(url)
    title_text = _normalize_text(title)
    h1_text = _normalize_text(h1)
    for token in COMMERCIAL_HARD_BLOCK_TOKENS:
        if token in url_text:
            return f"path:{token}"
        if token in title_text:
            return f"title:{token}"
        if token in h1_text:
            return f"h1:{token}"
    return ""


def _assess_candidate_page(url: str, title: str, h1: str, text: str, detection_method: str, threshold: int) -> _PageAssessment:
    normalized_text = _normalize_text(" ".join(part for part in (title, h1, text) if part))
    listing_signals = list(dict.fromkeys(signal for signal in PAGE_LISTING_SIGNALS if signal in normalized_text))
    residential_signals = list(dict.fromkeys(signal for signal in RESIDENTIAL_SIGNALS if signal in normalized_text))
    commercial_signals = list(dict.fromkeys(signal for signal in COMMERCIAL_SIGNALS if signal in normalized_text or signal in _url_haystack(url)))
    token_hits = set(_count_token_matches(_url_haystack(url), PRIORITY_TOKENS))
    token_hits.update(_count_token_matches(title, PRIORITY_TOKENS))
    token_hits.update(_count_token_matches(h1, PRIORITY_TOKENS))
    page_type, page_reason = _classify_page_type(url, normalized_text, residential_signals, commercial_signals)
    commercial_block_reason = _commercial_hard_block_reason(url, title, h1)
    commercial_hard_block = bool(commercial_block_reason)
    method_bonus = {"homepage_link": 12, "common_path": 8, "sitemap": 6}.get(detection_method, 0)
    confidence = min(100, 15 + len(token_hits) * 10 + len(listing_signals) * 8 + len(residential_signals) * 9 + method_bonus)

    if _reject_reason(url):
        return _PageAssessment(page_type, 0, listing_signals, residential_signals, commercial_signals, "rejected_non_html", "rejected", "non_html_asset", commercial_hard_block, commercial_block_reason)
    if commercial_hard_block or page_type == "commercial_listing":
        return _PageAssessment("commercial_listing", min(confidence, 45), listing_signals, residential_signals, commercial_signals, "commercial_only", "rejected", "commercial_only", True, commercial_block_reason or "commercial_signal")
    if page_type in {"property_detail", "project_page"}:
        return _PageAssessment(page_type, min(confidence, max(55, confidence)), listing_signals, residential_signals, commercial_signals, page_reason, "suspect", page_reason, commercial_hard_block, commercial_block_reason)
    if page_type == "listing_index" and len(residential_signals) >= 5 and confidence >= threshold:
        return _PageAssessment(page_type, confidence, listing_signals, residential_signals, commercial_signals, "residential_listing_index", "valid", "", commercial_hard_block, commercial_block_reason)
    if page_type == "listing_index":
        return _PageAssessment(page_type, min(confidence, threshold - 1), listing_signals, residential_signals, commercial_signals, "weak_residential_listing_index", "suspect", "weak_listing_evidence", commercial_hard_block, commercial_block_reason)
    if residential_signals and len(commercial_signals) < len(residential_signals):
        return _PageAssessment(page_type, min(confidence, threshold - 1), listing_signals, residential_signals, commercial_signals, "unknown_residential_shape", "suspect", "unknown_page_type", commercial_hard_block, commercial_block_reason)
    return _PageAssessment(page_type, min(confidence, 40), listing_signals, residential_signals, commercial_signals, page_reason, "missing", page_reason, commercial_hard_block, commercial_block_reason)


def _build_attempt(
    candidate: SourceCandidate,
    *,
    homepage_status: int,
    homepage_title: str,
    candidates_found_count: int,
    candidates_tested_count: int,
    best_candidate_url: str,
    page_assessment: _PageAssessment | None,
    detection_method: str,
    final_aanbod_url: str,
    final_status: str,
    rejection_reason: str,
    elapsed_ms: int,
) -> AanbodAuditAttempt:
    return AanbodAuditAttempt(
        office_name=candidate.office_name,
        website=candidate.website,
        root_domain=candidate.root_domain,
        gemeente=candidate.gemeente,
        final_status=final_status,
        final_aanbod_url=final_aanbod_url,
        confidence=page_assessment.confidence if page_assessment else 0,
        detection_method=detection_method,
        homepage_status=homepage_status,
        homepage_title=homepage_title,
        candidates_found_count=candidates_found_count,
        candidates_tested_count=candidates_tested_count,
        best_candidate_url=best_candidate_url,
        final_page_type=page_assessment.page_type if page_assessment else "unknown",
        listing_signals_count=len(page_assessment.listing_signals) if page_assessment else 0,
        residential_signals_count=len(page_assessment.residential_signals) if page_assessment else 0,
        commercial_signals_count=len(page_assessment.commercial_signals) if page_assessment else 0,
        elapsed_ms=elapsed_ms,
        residential_signals_found=page_assessment.residential_signals if page_assessment else [],
        commercial_signals_found=page_assessment.commercial_signals if page_assessment else [],
        page_quality_reason=page_assessment.quality_reason if page_assessment else rejection_reason,
        listing_signals_found=page_assessment.listing_signals if page_assessment else [],
        commercial_hard_block=page_assessment.commercial_hard_block if page_assessment else False,
        commercial_block_reason=page_assessment.commercial_block_reason if page_assessment else "",
        rejection_reason=rejection_reason,
    )


def _audit_single_candidate(page, candidate: SourceCandidate, threshold: int) -> AanbodAuditAttempt:
    started_at = perf_counter()
    website = _normalize_url(candidate.website)
    if not website:
        return _build_attempt(
            candidate,
            homepage_status=0,
            homepage_title="",
            candidates_found_count=0,
            candidates_tested_count=0,
            best_candidate_url="",
            page_assessment=None,
            detection_method="failed",
            final_aanbod_url="",
            final_status="missing",
            rejection_reason="missing_website",
            elapsed_ms=int((perf_counter() - started_at) * 1000),
        )

    try:
        homepage = _fetch_page(page, website)
    except (PlaywrightTimeoutError, PlaywrightError) as exc:
        return _build_attempt(
            candidate,
            homepage_status=0,
            homepage_title="",
            candidates_found_count=0,
            candidates_tested_count=0,
            best_candidate_url="",
            page_assessment=None,
            detection_method="failed",
            final_aanbod_url="",
            final_status="failed_fetch",
            rejection_reason=str(exc),
            elapsed_ms=int((perf_counter() - started_at) * 1000),
        )

    homepage_title, _, _, _ = _parse_page(homepage.html)
    if homepage.status != 200 or not homepage.html.strip():
        return _build_attempt(
            candidate,
            homepage_status=homepage.status,
            homepage_title=homepage_title,
            candidates_found_count=0,
            candidates_tested_count=0,
            best_candidate_url="",
            page_assessment=None,
            detection_method="failed",
            final_aanbod_url="",
            final_status="failed_fetch",
            rejection_reason=f"homepage_status={homepage.status}",
            elapsed_ms=int((perf_counter() - started_at) * 1000),
        )

    homepage_candidates = _candidate_urls_from_homepage(website, homepage.html)
    sitemap_candidates: list[str] = []
    try:
        sitemap_page = _fetch_page(page, urljoin(f"{website}/", "sitemap.xml"))
        if sitemap_page.status == 200:
            sitemap_candidates = _candidate_urls_from_sitemap(sitemap_page.html)
    except (PlaywrightTimeoutError, PlaywrightError):
        sitemap_candidates = []

    candidates_by_method: list[tuple[str, str]] = (
        [(url, "homepage_link") for url in homepage_candidates]
        + [(url, "sitemap") for url in sitemap_candidates]
        + [(url, "common_path") for url in _common_path_candidates(website)]
    )
    deduped: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for url, method in candidates_by_method:
        normalized = url.rstrip("/")
        if normalized in seen_urls:
            continue
        seen_urls.add(normalized)
        deduped.append((normalized, method))

    best_attempt: AanbodAuditAttempt | None = None
    status_rank = {"valid": 4, "suspect": 3, "rejected": 2, "missing": 1, "failed_fetch": 0}
    tested_count = 0

    for url, detection_method in deduped:
        if _reject_reason(url):
            continue
        tested_count += 1
        try:
            page_data = _fetch_page(page, url)
        except (PlaywrightTimeoutError, PlaywrightError):
            continue
        if page_data.status != 200 or not _is_html_page(page_data.content_type, page_data.url):
            continue
        title, h1, text, _ = _parse_page(page_data.html)
        assessment = _assess_candidate_page(page_data.url, title, h1, text, detection_method, threshold)
        attempt = _build_attempt(
            candidate,
            homepage_status=homepage.status,
            homepage_title=homepage_title,
            candidates_found_count=len(deduped),
            candidates_tested_count=tested_count,
            best_candidate_url=page_data.url,
            page_assessment=assessment,
            detection_method=detection_method,
            final_aanbod_url=page_data.url if assessment.final_status in {"valid", "suspect"} else "",
            final_status=assessment.final_status,
            rejection_reason=assessment.rejection_reason,
            elapsed_ms=int((perf_counter() - started_at) * 1000),
        )
        if best_attempt is None or (status_rank[attempt.final_status], attempt.confidence) > (
            status_rank[best_attempt.final_status],
            best_attempt.confidence,
        ):
            best_attempt = attempt

    if best_attempt is not None:
        best_attempt.elapsed_ms = int((perf_counter() - started_at) * 1000)
        return best_attempt

    return _build_attempt(
        candidate,
        homepage_status=homepage.status,
        homepage_title=homepage_title,
        candidates_found_count=len(deduped),
        candidates_tested_count=tested_count,
        best_candidate_url="",
        page_assessment=None,
        detection_method="failed",
        final_aanbod_url="",
        final_status="missing",
        rejection_reason="no_candidate_found",
        elapsed_ms=int((perf_counter() - started_at) * 1000),
    )


class AanbodAuditor:
    def __init__(self, *, confidence_threshold: int = 85) -> None:
        self.confidence_threshold = confidence_threshold

    def audit_candidates(self, candidates: list[SourceCandidate], *, max_audited_sites: int) -> list[AanbodAuditAttempt]:
        auditable = [
            candidate for candidate in candidates if candidate.website and candidate.aanbod_url_quality in {"missing", "suspect"}
        ][:max_audited_sites]
        if not auditable:
            return []
        if sync_playwright is None:
            raise RuntimeError("playwright is not installed; run `py -3.12 -m playwright install chromium` after pip install")

        attempts: list[AanbodAuditAttempt] = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            try:
                for candidate in auditable:
                    attempt = _audit_single_candidate(page, candidate, self.confidence_threshold)
                    attempts.append(attempt)
                    self._apply_attempt(candidate, attempt)
            finally:
                context.close()
                browser.close()
        self._mark_duplicates(attempts)
        return attempts

    def _mark_duplicates(self, attempts: list[AanbodAuditAttempt]) -> None:
        seen_valid_pairs: set[tuple[str, str]] = set()
        for attempt in attempts:
            if attempt.final_status != "valid" or not attempt.final_aanbod_url:
                continue
            key = ((attempt.root_domain or "").lower(), attempt.final_aanbod_url.rstrip("/").lower())
            if key in seen_valid_pairs:
                attempt.is_duplicate_audit_result = True
                continue
            seen_valid_pairs.add(key)

    def _apply_attempt(self, candidate: SourceCandidate, attempt: AanbodAuditAttempt) -> None:
        if attempt.final_status == "valid" and attempt.final_page_type == "listing_index":
            candidate.aanbod_url = attempt.final_aanbod_url
            candidate.aanbod_url_quality = "valid"
            candidate.aanbod_detection_method = "browser_audit"
            candidate.aanbod_detection_score = attempt.confidence
            candidate.aanbod_validation_reason = attempt.page_quality_reason
            candidate.needs_review = attempt.confidence < 90
            return
        if attempt.final_status == "suspect":
            if attempt.final_aanbod_url:
                candidate.aanbod_url = attempt.final_aanbod_url
            candidate.aanbod_url_quality = "suspect"
            candidate.aanbod_detection_method = "browser_audit"
            candidate.aanbod_detection_score = attempt.confidence
            candidate.aanbod_validation_reason = attempt.page_quality_reason
            candidate.needs_review = True
            return
        if attempt.final_status in {"missing", "rejected"}:
            candidate.aanbod_detection_method = "browser_audit"
            candidate.aanbod_detection_score = attempt.confidence
            candidate.aanbod_validation_reason = attempt.page_quality_reason or attempt.rejection_reason
            candidate.needs_review = True
            return
        if attempt.final_status == "failed_fetch":
            candidate.needs_review = True
