from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from urllib.parse import urljoin, urlsplit

from .config import (
    COMMON_AANBOD_PATHS,
    EXCLUDED_AANBOD_TOKENS,
    LIVE_AANBOD_MAX_SITEMAP_URLS,
    PAGE_LISTING_SIGNALS,
    VALID_AANBOD_SIGNALS,
)
from .models import SourceCandidate
from .website_fetcher import FetchResponse, WebsiteFetcher, dedupe_urls


@dataclass(slots=True)
class AanbodClassification:
    status: str
    reason: str
    url: str = ""
    score: int = 0
    detection_method: str = "failed"
    matched_signals: list[str] = field(default_factory=list)


@dataclass(slots=True)
class LiveAanbodResult:
    classification: AanbodClassification
    attempted: bool
    succeeded: bool
    failure_reason: str = ""
    failure_stage: str = "unknown"
    http_status_homepage: int = 0
    http_status_sitemap: int = 0
    tested_urls_count: int = 0
    best_candidate_url: str = ""
    best_candidate_reason: str = ""
    elapsed_ms: int = 0


def _normalize_url(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    return raw.rstrip("/")


def _haystack(url: str) -> str:
    parsed = urlsplit(url)
    return f"{parsed.netloc}{parsed.path}".lower()


def _text_haystack(text: str) -> str:
    return " ".join(text.lower().split())


def _match_tokens(haystack: str, tokens: tuple[str, ...]) -> list[str]:
    return [token for token in tokens if token in haystack]


def _url_priority(url: str) -> int:
    haystack = _haystack(url)
    score = 0
    score += len(_match_tokens(haystack, VALID_AANBOD_SIGNALS)) * 15
    score -= len(_match_tokens(haystack, EXCLUDED_AANBOD_TOKENS)) * 25
    return score


def _score_listing_page(url: str, response: FetchResponse) -> AanbodClassification:
    normalized = _normalize_url(response.url or url)
    if response.status_code != 200:
        return AanbodClassification(
            status="rejected",
            reason=f"status_code={response.status_code or 0}",
            url=normalized or _normalize_url(url),
            score=0,
        )
    text = _text_haystack(response.text)
    if not text:
        return AanbodClassification(status="rejected", reason="empty page", url=normalized, score=0)

    url_excluded = _match_tokens(_haystack(normalized), EXCLUDED_AANBOD_TOKENS)
    text_excluded = _match_tokens(text, EXCLUDED_AANBOD_TOKENS)
    if url_excluded or text_excluded:
        token = (url_excluded or text_excluded)[0]
        return AanbodClassification(
            status="rejected",
            reason=f"contains excluded token '{token}'",
            url=normalized,
            score=0,
        )

    matched_signals = [signal for signal in PAGE_LISTING_SIGNALS if signal in text and signal != "funda"]
    unique_signals = list(dict.fromkeys(matched_signals))
    url_signals = _match_tokens(_haystack(normalized), VALID_AANBOD_SIGNALS)
    signal_count = len(unique_signals)

    score = min(100, signal_count * 18 + len(url_signals) * 10 + 10)
    if signal_count >= 2:
        return AanbodClassification(
            status="valid",
            reason=f"listing signals={','.join(unique_signals[:5])}",
            url=normalized,
            score=score,
            matched_signals=unique_signals,
        )
    if url_signals or signal_count == 1:
        return AanbodClassification(
            status="suspect",
            reason="possible aanbod page but insufficient listing signals",
            url=normalized,
            score=min(score, 59),
            matched_signals=unique_signals,
        )
    return AanbodClassification(
        status="missing",
        reason="missing listing signals",
        url=normalized,
        score=min(score, 30),
        matched_signals=unique_signals,
    )


def classify_aanbod_url(url: str | None) -> AanbodClassification:
    normalized = _normalize_url(url)
    if not normalized:
        return AanbodClassification(status="missing", reason="missing aanbod_url")

    haystack = _haystack(normalized)
    matched_excluded = _match_tokens(haystack, EXCLUDED_AANBOD_TOKENS)
    if matched_excluded:
        status = "rejected" if matched_excluded[0] in {"contact", "privacy", "about"} else "suspect"
        return AanbodClassification(
            status=status,
            reason=f"contains excluded token '{matched_excluded[0]}'",
            url=normalized,
            score=0 if status == "rejected" else 25,
            detection_method="existing_seed_url",
        )

    matched_valid = _match_tokens(haystack, VALID_AANBOD_SIGNALS)
    if matched_valid:
        return AanbodClassification(
            status="valid",
            reason=f"url contains listing signal '{matched_valid[0]}'",
            url=normalized,
            score=75,
            detection_method="existing_seed_url",
        )

    return AanbodClassification(
        status="suspect",
        reason="missing listing signal",
        url=normalized,
        score=30,
        detection_method="existing_seed_url",
    )


def suggest_common_aanbod_paths(website: str | None) -> list[str]:
    normalized = _normalize_url(website)
    if not normalized:
        return []
    return [urljoin(f"{normalized}/", path.lstrip("/")) for path in COMMON_AANBOD_PATHS]


def _homepage_candidates(fetcher: WebsiteFetcher, website: str, html: str) -> list[str]:
    links = fetcher.extract_internal_links(website, html)
    ranked = sorted(
        (link for link in links if _url_priority(link) > 0),
        key=lambda link: (_url_priority(link), len(link)),
        reverse=True,
    )
    return ranked[:20]


def _sitemap_candidates(fetcher: WebsiteFetcher, website: str) -> list[str]:
    sitemap_url = urljoin(f"{website}/", "sitemap.xml")
    response = fetcher.fetch(sitemap_url)
    if response.status_code != 200 or not response.text.strip():
        return []
    urls = fetcher.parse_sitemap_urls(response.text, limit=LIVE_AANBOD_MAX_SITEMAP_URLS)
    ranked = sorted(
        (url for url in urls if _url_priority(url) > 0),
        key=lambda url: (_url_priority(url), len(url)),
        reverse=True,
    )
    return ranked[:20]


def _classify_candidate_url(
    fetcher: WebsiteFetcher,
    url: str,
    detection_method: str,
) -> AanbodClassification:
    response = fetcher.fetch(url)
    classification = _score_listing_page(url, response)
    classification.detection_method = detection_method
    if classification.status == "valid":
        bonuses = {
            "homepage_link": 12,
            "sitemap": 8,
            "common_path": 5,
            "existing_seed_url": 15,
        }
        classification.score = min(100, classification.score + bonuses.get(detection_method, 0))
    return classification


def _failure_stage_from_error(error: str, default_stage: str) -> str:
    haystack = (error or "").lower()
    if "timed out" in haystack or "timeout" in haystack:
        return "timeout"
    if "ssl" in haystack or "certificate" in haystack or "tls" in haystack:
        return "ssl"
    if "robots" in haystack:
        return "robots"
    return default_stage if default_stage in {
        "homepage_fetch",
        "sitemap_fetch",
        "common_path_probe",
        "validation",
        "timeout",
        "ssl",
        "robots",
        "unknown",
    } else "unknown"


def _pick_best(classifications: list[AanbodClassification]) -> AanbodClassification:
    if not classifications:
        return AanbodClassification(
            status="missing",
            reason="no aanbod candidate matched",
            detection_method="failed",
            score=0,
        )
    return max(
        classifications,
        key=lambda item: (
            {"valid": 3, "suspect": 2, "missing": 1, "rejected": 0}.get(item.status, 0),
            item.score,
        ),
    )


def detect_live_aanbod_url(
    candidate: SourceCandidate,
    fetcher: WebsiteFetcher,
) -> LiveAanbodResult:
    started_at = perf_counter()
    website = _normalize_url(candidate.website)
    if not website:
        return LiveAanbodResult(
            classification=AanbodClassification(
                status="missing",
                reason="missing website",
                detection_method="failed",
                score=0,
            ),
            attempted=False,
            succeeded=False,
            failure_reason="missing website",
            failure_stage="unknown",
            elapsed_ms=int((perf_counter() - started_at) * 1000),
        )

    homepage = fetcher.fetch(website)
    if homepage.status_code != 200 or not homepage.text.strip():
        failure_reason = homepage.error or f"status_code={homepage.status_code or 0}"
        return LiveAanbodResult(
            classification=AanbodClassification(
                status="rejected",
                reason=f"homepage fetch failed: status_code={homepage.status_code or 0}",
                url=website,
                detection_method="failed",
                score=0,
            ),
            attempted=True,
            succeeded=False,
            failure_reason=failure_reason,
            failure_stage=_failure_stage_from_error(failure_reason, "homepage_fetch"),
            http_status_homepage=homepage.status_code,
            elapsed_ms=int((perf_counter() - started_at) * 1000),
        )

    classifications: list[AanbodClassification] = []
    tested_urls: list[str] = []
    sitemap_status_code = 0

    existing = classify_aanbod_url(candidate.aanbod_url)
    if candidate.aanbod_url and existing.status == "valid":
        validated_existing = _classify_candidate_url(fetcher, candidate.aanbod_url, "existing_seed_url")
        if validated_existing.status in {"valid", "suspect"}:
            classifications.append(validated_existing)
        tested_urls.append(candidate.aanbod_url)

    for url in _homepage_candidates(fetcher, website, homepage.text):
        classifications.append(_classify_candidate_url(fetcher, url, "homepage_link"))
        tested_urls.append(url)

    sitemap_url = urljoin(f"{website}/", "sitemap.xml")
    sitemap_response = fetcher.fetch(sitemap_url)
    sitemap_status_code = sitemap_response.status_code
    sitemap_urls: list[str] = []
    if sitemap_response.status_code == 200 and sitemap_response.text.strip():
        sitemap_urls = fetcher.parse_sitemap_urls(sitemap_response.text, limit=LIVE_AANBOD_MAX_SITEMAP_URLS)
        sitemap_urls = sorted(
            (url for url in sitemap_urls if _url_priority(url) > 0),
            key=lambda url: (_url_priority(url), len(url)),
            reverse=True,
        )[:20]
    for url in sitemap_urls:
        classifications.append(_classify_candidate_url(fetcher, url, "sitemap"))
        tested_urls.append(url)

    for url in suggest_common_aanbod_paths(website):
        classifications.append(_classify_candidate_url(fetcher, url, "common_path"))
        tested_urls.append(url)

    best = _pick_best(dedupe_classifications(classifications))
    tested_count = len(dedupe_urls(tested_urls))
    if best.status in {"valid", "suspect"}:
        failure_stage = "unknown"
        failure_reason = ""
    else:
        failure_reason = best.reason
        if sitemap_response.error:
            failure_stage = _failure_stage_from_error(sitemap_response.error, "sitemap_fetch")
        elif best.detection_method == "common_path":
            failure_stage = "common_path_probe"
        elif best.detection_method in {"homepage_link", "sitemap", "existing_seed_url"}:
            failure_stage = "validation"
        elif sitemap_response.status_code and sitemap_response.status_code != 200:
            failure_stage = "sitemap_fetch"
        else:
            failure_stage = "unknown"
    return LiveAanbodResult(
        classification=best,
        attempted=True,
        succeeded=best.status in {"valid", "suspect"},
        failure_reason=failure_reason,
        failure_stage=failure_stage,
        http_status_homepage=homepage.status_code,
        http_status_sitemap=sitemap_status_code,
        tested_urls_count=tested_count,
        best_candidate_url=best.url,
        best_candidate_reason=best.reason,
        elapsed_ms=int((perf_counter() - started_at) * 1000),
    )


def dedupe_classifications(classifications: list[AanbodClassification]) -> list[AanbodClassification]:
    best_by_url: dict[str, AanbodClassification] = {}
    for item in classifications:
        key = item.url or item.reason
        current = best_by_url.get(key)
        if current is None or (item.score, item.status) > (current.score, current.status):
            best_by_url[key] = item
    return list(best_by_url.values())


def apply_aanbod_classification(candidate: SourceCandidate, classification: AanbodClassification) -> None:
    if classification.status in {"valid", "suspect"} and classification.url:
        candidate.aanbod_url = classification.url
    candidate.aanbod_url_quality = classification.status if classification.status != "rejected" else "missing"
    candidate.aanbod_detection_method = classification.detection_method
    candidate.aanbod_detection_score = classification.score
    candidate.aanbod_validation_reason = classification.reason
