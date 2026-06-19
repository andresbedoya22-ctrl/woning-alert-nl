from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
import re

from domek_wonen.portals.live_fetch import FetchResult, fetch_url, polite_sleep
from domek_wonen.portals.models import SourceStatus
from domek_wonen.portals.portal_inventory_spike import build_default_output_dir, normalize_text

DEFAULT_OUTPUT_ROOT = Path("data") / "diagnostics" / "portal_inventory"
STOP_SOURCE_STATUSES = {
    SourceStatus.HTTP_403,
    SourceStatus.HTTP_429,
    SourceStatus.BLOCKED_CAPTCHA,
    SourceStatus.PERMISSION_REQUIRED,
}


@dataclass(slots=True)
class HuislijnUrlProbe:
    label: str
    city_query: str
    url: str


@dataclass(slots=True)
class HuislijnUrlProbeResult:
    label: str
    city_query: str
    url: str
    status_code: int | None
    source_status: str
    elapsed_ms: int
    content_length: int
    has_listing_like_links: bool
    has_json_ld: bool
    has_next_data_or_embedded_state: bool
    has_search_form: bool
    evidence_snippet: str
    recommendation: str


@dataclass(slots=True)
class HuislijnUrlDiscoveryResult:
    generated_at: str
    max_requests: int
    requests_used: int
    stopped_early: bool
    stop_reason: str
    probe_results: list[HuislijnUrlProbeResult]


def slugify_city(city: str) -> str:
    return normalize_text(city).lower().replace(" ", "-")


def build_candidate_probes(cities: list[str]) -> list[HuislijnUrlProbe]:
    probes = [HuislijnUrlProbe(label="homepage", city_query="", url="https://www.huislijn.nl/")]
    for city in cities:
        city_slug = slugify_city(city)
        probes.extend(
            [
                HuislijnUrlProbe(
                    label="legacy_koopwoning_nederland",
                    city_query=city,
                    url=f"https://www.huislijn.nl/koopwoning/nederland/{city_slug}",
                ),
                HuislijnUrlProbe(
                    label="koopwoningen_city",
                    city_query=city,
                    url=f"https://www.huislijn.nl/koopwoningen/{city_slug}",
                ),
                HuislijnUrlProbe(
                    label="koop_city",
                    city_query=city,
                    url=f"https://www.huislijn.nl/koop/{city_slug}",
                ),
            ]
        )
    return probes


def detect_listing_like_links(html: str) -> bool:
    lowered = html.lower()
    patterns = (
        r'href="https://www\.huislijn\.nl/koopwoning/[^"]+"',
        r'href="/koopwoning/[^"]+"',
        r'class="[^"]*listing-card[^"]*"',
        r'data-url="https://www\.huislijn\.nl/koopwoning/[^"]+"',
    )
    return any(re.search(pattern, lowered) for pattern in patterns)


def detect_json_ld(html: str) -> bool:
    return 'type="application/ld+json"' in html.lower() or "type='application/ld+json'" in html.lower()


def detect_embedded_state(html: str) -> bool:
    lowered = html.lower()
    markers = (
        "__next_data__",
        "__nuxt__",
        "window.__initial_state__",
        "window.__nuxt__",
        "application/json",
        '"props":',
        '"pageprops":',
    )
    return any(marker in lowered for marker in markers)


def detect_search_form(html: str) -> bool:
    lowered = html.lower()
    return "<form" in lowered and any(marker in lowered for marker in ("search", "zoek", "plaats", "city"))


def extract_evidence_snippet(html: str, fetch_result: FetchResult) -> str:
    normalized_html = normalize_text(html)
    snippet_markers = (
        "captcha",
        "log in",
        "sign in",
        "javascript",
        "zoek",
        "search",
        "koopwoning",
        "koopwoningen",
    )
    lowered = normalized_html.lower()
    for marker in snippet_markers:
        index = lowered.find(marker)
        if index >= 0:
            start = max(0, index - 50)
            end = min(len(normalized_html), index + 140)
            return normalized_html[start:end][:180]
    if fetch_result.error_message:
        return normalize_text(fetch_result.error_message)[:180]
    return normalized_html[:180]


def classify_recommendation(fetch_result: FetchResult, html: str) -> str:
    if fetch_result.source_status in STOP_SOURCE_STATUSES:
        return "blocked"
    if fetch_result.status_code == 410:
        return "wrong_url_410"
    if fetch_result.source_status == SourceStatus.REQUIRES_JS:
        return "requires_js"

    has_listing_like_links = detect_listing_like_links(html)
    has_json_ld = detect_json_ld(html)
    has_embedded_state = detect_embedded_state(html)
    if has_listing_like_links or has_json_ld:
        return "candidate_search_url"
    if has_embedded_state:
        return "requires_js"
    return "needs_manual_review"


def summarize_probe(probe: HuislijnUrlProbe, fetch_result: FetchResult) -> HuislijnUrlProbeResult:
    html = fetch_result.html
    return HuislijnUrlProbeResult(
        label=probe.label,
        city_query=probe.city_query,
        url=probe.url,
        status_code=fetch_result.status_code,
        source_status=fetch_result.source_status.value,
        elapsed_ms=fetch_result.elapsed_ms,
        content_length=len(html.encode("utf-8", errors="replace")),
        has_listing_like_links=detect_listing_like_links(html),
        has_json_ld=detect_json_ld(html),
        has_next_data_or_embedded_state=detect_embedded_state(html),
        has_search_form=detect_search_form(html),
        evidence_snippet=extract_evidence_snippet(html, fetch_result),
        recommendation=classify_recommendation(fetch_result, html),
    )


def run_huislijn_url_discovery(
    cities: list[str],
    delay_seconds: float = 3.0,
    timeout_seconds: int = 20,
    max_requests: int = 10,
) -> HuislijnUrlDiscoveryResult:
    probe_results: list[HuislijnUrlProbeResult] = []
    stopped_early = False
    stop_reason = ""
    requests_used = 0
    probes = build_candidate_probes(cities)

    for index, probe in enumerate(probes):
        if requests_used >= max_requests:
            stopped_early = True
            stop_reason = f"max_requests_reached={max_requests}"
            break

        fetch_result = fetch_url(probe.url, timeout_seconds=timeout_seconds)
        requests_used += 1
        probe_result = summarize_probe(probe, fetch_result)
        probe_results.append(probe_result)

        if fetch_result.source_status in STOP_SOURCE_STATUSES:
            stopped_early = True
            stop_reason = f"stop_source_status={fetch_result.source_status.value}"
            break

        if index < len(probes) - 1 and requests_used < max_requests:
            polite_sleep(delay_seconds)

    return HuislijnUrlDiscoveryResult(
        generated_at=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
        max_requests=max_requests,
        requests_used=requests_used,
        stopped_early=stopped_early,
        stop_reason=stop_reason,
        probe_results=probe_results,
    )


def write_outputs(result: HuislijnUrlDiscoveryResult, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates_path = output_dir / "huislijn_url_candidates.csv"
    report_path = output_dir / "huislijn_url_discovery_report.md"

    with candidates_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = list(HuislijnUrlProbeResult.__dataclass_fields__.keys())
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for probe_result in result.probe_results:
            writer.writerow(asdict(probe_result))

    report_path.write_text(generate_markdown_report(result), encoding="utf-8")
    return {"report_md": report_path, "candidates_csv": candidates_path}


def generate_markdown_report(result: HuislijnUrlDiscoveryResult) -> str:
    lines = [
        "# Huislijn URL Discovery Spike",
        "",
        f"Generated at: {result.generated_at}",
        f"Requests used: {result.requests_used}/{result.max_requests}",
        f"Stopped early: {str(result.stopped_early).lower()}",
    ]
    if result.stop_reason:
        lines.append(f"Stop reason: {result.stop_reason}")
    lines.append("")

    recommendation_counts: dict[str, int] = {}
    for probe_result in result.probe_results:
        recommendation_counts[probe_result.recommendation] = recommendation_counts.get(probe_result.recommendation, 0) + 1

    lines.append("## Recommendation Summary")
    for recommendation, count in sorted(recommendation_counts.items()):
        lines.append(f"- {recommendation}: {count}")
    lines.append("")

    for probe_result in result.probe_results:
        city_label = probe_result.city_query or "homepage"
        lines.extend(
            [
                f"## {probe_result.label} - {city_label}",
                f"- url: {probe_result.url}",
                f"- status_code: {probe_result.status_code}",
                f"- source_status: {probe_result.source_status}",
                f"- elapsed_ms: {probe_result.elapsed_ms}",
                f"- content_length: {probe_result.content_length}",
                f"- has_listing_like_links: {str(probe_result.has_listing_like_links).lower()}",
                f"- has_json_ld: {str(probe_result.has_json_ld).lower()}",
                f"- has_next_data_or_embedded_state: {str(probe_result.has_next_data_or_embedded_state).lower()}",
                f"- has_search_form: {str(probe_result.has_search_form).lower()}",
                f"- recommendation: {probe_result.recommendation}",
                f"- evidence_snippet: {probe_result.evidence_snippet or '(empty)'}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def resolve_output_dir(output_dir: Path | None, generated_at: str) -> Path:
    if output_dir is not None:
        return output_dir
    return build_default_output_dir(DEFAULT_OUTPUT_ROOT, generated_at)
