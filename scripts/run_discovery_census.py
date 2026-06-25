from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
import os
from pathlib import Path
import random
import sys
import time

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.discovery.census import DomainClassification, DiscoveryStrategy, classify_domain
from domek_wonen.discovery.discovery_artifacts import resolve_makelaar_sources_master
from domek_wonen.runtime_settings import load_runtime_settings


DEFAULT_OUTPUT_ROOT = BASE_DIR / "data" / "diagnostics" / "discovery_census"
DISCOVERABLE_STRATEGIES = {
    DiscoveryStrategy.sitemap_with_listings,
    DiscoveryStrategy.wp_json,
    DiscoveryStrategy.listing_html,
}
INVENTORY_COLUMNS = (
    "domain",
    "aanbod_url_used",
    "robots_status",
    "robots_crawl_delay",
    "discovery_strategy",
    "cms_fingerprint_guess",
    "sitemap_found",
    "sitemap_has_listing_urls",
    "wp_json_listings_found",
    "structured_channel_open",
    "html_blocked_but_structured_open",
    "listing_url_pattern",
    "card_fields_extractable",
    "needs_js",
    "requests_used",
    "recommended_action",
    "blocker_reason",
)


def _is_truthy(value: str) -> bool:
    return value.strip().lower() in {"true", "1", "yes"}


def utc_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    settings = load_runtime_settings(load_dotenv_file=False)
    parser = argparse.ArgumentParser(description="Run a discovery census over a sampled set of makelaar domains.")
    parser.add_argument("--registry", default=None, help="Optional explicit makelaar_sources_master.csv path")
    parser.add_argument("--domain-column", default="root_domain", help="CSV column that contains the clean root domain")
    parser.add_argument("--aanbod-url-column", default="aanbod_url", help="CSV column that contains the known aanbod URL")
    parser.add_argument("--sample", type=int, default=30, help="Number of unique domains to classify")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible domain sampling")
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=float(settings.min_request_interval_seconds),
        help="Minimum delay between domains after each classification",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=float(settings.request_timeout_seconds),
        help="Per-request timeout shown in the run config",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional explicit output directory (default: data/diagnostics/discovery_census/{timestamp})",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show config and sampled domains without network requests")
    return parser.parse_args(argv)


def resolve_registry_path(registry: str | None) -> Path:
    explicit_path = Path(registry) if registry else None
    return resolve_makelaar_sources_master(input_path=explicit_path, restore_latest=True)


def load_registry_data(
    registry_path: Path,
    domain_column: str,
    aanbod_url_column: str,
) -> tuple[list[str], dict[str, str]]:
    with registry_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        if domain_column not in fieldnames:
            raise ValueError(f"Domain column {domain_column!r} not found in {registry_path}")

        prefer_active = "is_active" in fieldnames
        has_aanbod_column = aanbod_url_column in fieldnames
        domains: list[str] = []
        aanbod_urls_by_domain: dict[str, str] = {}
        seen: set[str] = set()
        for row in reader:
            if prefer_active and not _is_truthy(str(row.get("is_active", ""))):
                continue
            domain = str(row.get(domain_column, "")).strip().lower()
            if not domain or domain in seen:
                continue
            seen.add(domain)
            domains.append(domain)
            if has_aanbod_column:
                aanbod_url = str(row.get(aanbod_url_column, "")).strip()
                if aanbod_url:
                    aanbod_urls_by_domain[domain] = aanbod_url
    return domains, aanbod_urls_by_domain


def load_registry_domains(registry_path: Path, domain_column: str) -> list[str]:
    domains, _ = load_registry_data(registry_path, domain_column, "aanbod_url")
    return domains


def sample_domains(domains: list[str], sample_size: int, seed: int) -> tuple[list[str], bool]:
    if sample_size <= 0:
        raise ValueError("--sample must be > 0")
    if len(domains) <= sample_size:
        return list(domains), True
    rng = random.Random(seed)
    return rng.sample(domains, sample_size), False


def classification_to_row(classification: DomainClassification, *, aanbod_url_used: bool = False) -> dict[str, object]:
    row = asdict(classification)
    row["aanbod_url_used"] = "yes" if aanbod_url_used else "no"
    row["discovery_strategy"] = classification.discovery_strategy.value
    row["card_fields_extractable"] = ",".join(classification.card_fields_extractable)
    return row


def failure_classification(domain: str, error: Exception) -> DomainClassification:
    return DomainClassification(
        domain=domain,
        robots_status="error",
        robots_crawl_delay=0.0,
        discovery_strategy=DiscoveryStrategy.blocked,
        cms_fingerprint_guess="unknown",
        sitemap_found=False,
        sitemap_has_listing_urls=False,
        wp_json_listings_found=False,
        structured_channel_open=False,
        html_blocked_but_structured_open=False,
        listing_url_pattern=None,
        card_fields_extractable=[],
        needs_js=False,
        requests_used=0,
        recommended_action="skip_blocked",
        blocker_reason=f"exception:{error.__class__.__name__}",
    )


def classify_domains(
    domains: list[str],
    *,
    classify=classify_domain,
    aanbod_urls_by_domain: dict[str, str] | None = None,
    delay_seconds: float,
    timeout_seconds: float | None = None,
    sleep=time.sleep,
) -> list[DomainClassification]:
    results: list[DomainClassification] = []
    aanbod_urls_by_domain = aanbod_urls_by_domain or {}
    previous_timeout = os.environ.get("WNA_REQUEST_TIMEOUT_SECONDS")
    try:
        if timeout_seconds is not None:
            env_timeout = int(timeout_seconds) if float(timeout_seconds).is_integer() else timeout_seconds
            os.environ["WNA_REQUEST_TIMEOUT_SECONDS"] = str(env_timeout)

        for index, domain in enumerate(domains):
            try:
                known_aanbod_url = aanbod_urls_by_domain.get(domain)
                if known_aanbod_url:
                    classification = classify(domain, known_aanbod_url=known_aanbod_url)
                else:
                    classification = classify(domain)
            except Exception as exc:  # pragma: no cover - exercised via tests through injected classifier
                classification = failure_classification(domain, exc)
            results.append(classification)

            if index < len(domains) - 1:
                wait_seconds = max(delay_seconds, float(classification.robots_crawl_delay))
                if wait_seconds > 0:
                    sleep(wait_seconds)
    finally:
        if timeout_seconds is not None:
            if previous_timeout is None:
                os.environ.pop("WNA_REQUEST_TIMEOUT_SECONDS", None)
            else:
                os.environ["WNA_REQUEST_TIMEOUT_SECONDS"] = previous_timeout
    return results


def percent(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round((count / total) * 100, 2)


def covered_reason(classification: DomainClassification) -> str:
    if classification.blocker_reason:
        return classification.blocker_reason
    if classification.needs_js:
        return "needs_js"
    return classification.discovery_strategy.value


def compute_summary(classifications: list[DomainClassification]) -> dict[str, object]:
    total = len(classifications)
    strategy_counts = Counter(item.discovery_strategy.value for item in classifications)
    cms_counts = Counter(item.cms_fingerprint_guess for item in classifications)
    discoverable_count = sum(1 for item in classifications if item.discovery_strategy in DISCOVERABLE_STRATEGIES)
    blocked_count = strategy_counts.get(DiscoveryStrategy.blocked.value, 0)
    robots_disallow_count = strategy_counts.get(DiscoveryStrategy.robots_disallow.value, 0)
    needs_js_count = strategy_counts.get(DiscoveryStrategy.listing_js.value, 0)
    discoverable_percent = percent(discoverable_count, total)

    if discoverable_percent >= 60.0:
        verdict = "VERDE: construir Bloques 2-7"
    elif discoverable_percent >= 30.0:
        verdict = "AMARILLO: construir verdes + decidir JS"
    else:
        verdict = "ROJO: track comercial (Realworks/Kolibri)"

    uncovered = [
        {"domain": item.domain, "strategy": item.discovery_strategy.value, "reason": covered_reason(item)}
        for item in classifications
        if item.discovery_strategy not in DISCOVERABLE_STRATEGIES
    ]
    return {
        "total": total,
        "strategy_counts": dict(sorted(strategy_counts.items())),
        "cms_counts": dict(sorted(cms_counts.items())),
        "discoverable_count": discoverable_count,
        "discoverable_percent": discoverable_percent,
        "blocked_percent": percent(blocked_count, total),
        "robots_disallow_percent": percent(robots_disallow_count, total),
        "needs_js_percent": percent(needs_js_count, total),
        "uncovered": uncovered,
        "verdict": verdict,
    }


def render_report(
    *,
    run_id: str,
    generated_at: str,
    registry_path: Path,
    sample_size: int,
    seed: int,
    used_all_domains: bool,
    domains: list[str],
    summary: dict[str, object],
    aanbod_registry_count: int,
) -> str:
    lines = [
        "# Discovery Census Report",
        "",
        f"- run_id: {run_id}",
        f"- generated_at: {generated_at}",
        f"- registry: {registry_path}",
        f"- sample_size: {sample_size}",
        f"- seed: {seed}",
        f"- used_all_domains: {'yes' if used_all_domains else 'no'}",
        f"- sampled_domains: {len(domains)}",
        f"- registry_aanbod_url_domains: {aanbod_registry_count}",
        "",
        "## Distribution by discovery_strategy",
    ]
    for strategy, count in summary["strategy_counts"].items():
        lines.append(f"- {strategy}: {count}")

    lines.extend(
        [
            "",
            f"- % robots_disallow: {summary['robots_disallow_percent']}",
            f"- % blocked: {summary['blocked_percent']}",
            f"- % needs_js: {summary['needs_js_percent']}",
            f"- % discoverable: {summary['discoverable_percent']}",
            f"- discoverable_domains: {summary['discoverable_count']}",
            "",
            "## Distribution by cms_fingerprint_guess",
        ]
    )
    for cms_name, count in summary["cms_counts"].items():
        lines.append(f"- {cms_name}: {count}")

    lines.extend(["", "## Uncovered domains"])
    uncovered = summary["uncovered"]
    if uncovered:
        for item in uncovered:
            lines.append(f"- {item['domain']}: {item['strategy']} ({item['reason']})")
    else:
        lines.append("- none")

    lines.extend(["", "## Verdict", f"- {summary['verdict']}"])
    return "\n".join(lines) + "\n"


def ensure_output_dir(output_dir: str | None, run_id: str) -> Path:
    if output_dir:
        path = Path(output_dir)
    else:
        path = DEFAULT_OUTPUT_ROOT / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_outputs(
    output_dir: Path,
    classifications: list[DomainClassification],
    report_text: str,
    *,
    aanbod_urls_by_domain: dict[str, str] | None = None,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    inventory_path = output_dir / "census_inventory.csv"
    report_path = output_dir / "census_report.md"
    aanbod_urls_by_domain = aanbod_urls_by_domain or {}

    with inventory_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=INVENTORY_COLUMNS)
        writer.writeheader()
        for classification in classifications:
            writer.writerow(
                classification_to_row(
                    classification,
                    aanbod_url_used=classification.domain in aanbod_urls_by_domain,
                )
            )

    report_path.write_text(report_text, encoding="utf-8")
    return inventory_path, report_path


def print_dry_run(registry_path: Path, args: argparse.Namespace, domains: list[str], used_all_domains: bool) -> None:
    print("Discovery census dry-run", flush=True)
    print(f"registry={registry_path}", flush=True)
    print(
        f"domain_column={args.domain_column} sample={args.sample} sampled_domains={len(domains)} seed={args.seed} "
        f"delay_seconds={args.delay_seconds} timeout_seconds={args.timeout_seconds} used_all_domains={used_all_domains}",
        flush=True,
    )
    for domain in domains:
        print(domain, flush=True)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    registry_path = resolve_registry_path(args.registry)
    domains, aanbod_urls_by_domain = load_registry_data(
        registry_path,
        args.domain_column,
        args.aanbod_url_column,
    )
    sampled_domains, used_all_domains = sample_domains(domains, args.sample, args.seed)

    if args.dry_run:
        print(f"registry_aanbod_url_domains={sum(1 for domain in sampled_domains if domain in aanbod_urls_by_domain)}", flush=True)
        print_dry_run(registry_path, args, sampled_domains, used_all_domains)
        return 0

    run_id = utc_timestamp()
    generated_at = datetime.now(UTC).isoformat()
    classifications = classify_domains(
        sampled_domains,
        aanbod_urls_by_domain={domain: aanbod_urls_by_domain[domain] for domain in sampled_domains if domain in aanbod_urls_by_domain},
        delay_seconds=args.delay_seconds,
        timeout_seconds=args.timeout_seconds,
    )
    summary = compute_summary(classifications)
    report_text = render_report(
        run_id=run_id,
        generated_at=generated_at,
        registry_path=registry_path,
        sample_size=args.sample,
        seed=args.seed,
        used_all_domains=used_all_domains,
        domains=sampled_domains,
        summary=summary,
        aanbod_registry_count=sum(1 for domain in sampled_domains if domain in aanbod_urls_by_domain),
    )
    output_dir = ensure_output_dir(args.output_dir, run_id)
    inventory_path, report_path = write_outputs(
        output_dir,
        classifications,
        report_text,
        aanbod_urls_by_domain={domain: aanbod_urls_by_domain[domain] for domain in sampled_domains if domain in aanbod_urls_by_domain},
    )

    print(inventory_path, flush=True)
    print(report_path, flush=True)
    print(summary["verdict"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
