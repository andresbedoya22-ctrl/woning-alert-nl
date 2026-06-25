from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
import sys
import time

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.harvest.mini_harvest import (
    DISCOVERABLE_STRATEGIES,
    MiniHarvestResult,
    format_rate,
    generate_markdown_report,
    harvest_domain_sample,
    summarize_result,
    summarize_run,
    write_run_outputs,
)
from domek_wonen.runtime_settings import load_runtime_settings


DEFAULT_OUTPUT_ROOT = BASE_DIR / "data" / "diagnostics" / "mini_harvest"
CENSUS_ROOT = BASE_DIR / "data" / "diagnostics" / "discovery_census"
SOURCE_MASTER_FALLBACK = BASE_DIR / "data" / "discovery" / "runs" / "20260614T122022Z" / "makelaar_sources_master.csv"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a bounded mini-harvest over discoverable census domains.")
    parser.add_argument("--census-run", default=None, help="Census run id under data/diagnostics/discovery_census.")
    parser.add_argument("--max-listings", type=int, default=10, help="Maximum listings to keep per domain.")
    parser.add_argument("--max-fichas", type=int, default=5, help="Maximum detail pages to fetch for sitemap/wp-json.")
    parser.add_argument("--delay-seconds", type=float, default=None, help="Delay between domains.")
    parser.add_argument("--dry-run", action="store_true", help="Resolve targets and write a report without network fetches.")
    return parser.parse_args(argv)


def _latest_census_run() -> Path:
    candidates = [path for path in CENSUS_ROOT.iterdir() if (path / "census_inventory.csv").exists()]
    if not candidates:
        raise FileNotFoundError("No census runs found under data/diagnostics/discovery_census")
    return sorted(candidates, key=lambda item: item.name)[-1]


def _resolve_census_run(run_id: str | None) -> Path:
    if run_id:
        candidate = CENSUS_ROOT / run_id
        if not (candidate / "census_inventory.csv").exists():
            raise FileNotFoundError(f"Missing census run: {candidate}")
        return candidate
    return _latest_census_run()


def _read_csv(path: Path) -> list[dict[str, str]]:
    import csv

    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _resolve_source_master() -> Path:
    latest_candidate = BASE_DIR / "data" / "discovery" / "latest" / "makelaar_sources_master.csv"
    if latest_candidate.exists():
        return latest_candidate
    if SOURCE_MASTER_FALLBACK.exists():
        return SOURCE_MASTER_FALLBACK
    raise FileNotFoundError("No makelaar_sources_master.csv available")


def _load_source_lookup(source_master_path: Path) -> dict[str, dict[str, str]]:
    rows = _read_csv(source_master_path)
    lookup: dict[str, dict[str, str]] = {}
    for row in rows:
        domain = (row.get("root_domain") or "").strip().lower()
        if domain and domain not in lookup:
            lookup[domain] = row
    return lookup


def _discoverable_rows(census_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        row
        for row in census_rows
        if (row.get("discovery_strategy") or "") in DISCOVERABLE_STRATEGIES
        and (row.get("discovery_strategy") or "") not in {"iframe_only", "blocked"}
    ]


def _resolve_aanbod_url(domain: str, row: dict[str, str], source_lookup: dict[str, dict[str, str]]) -> str | None:
    source_row = source_lookup.get(domain, {})
    aanbod_url = (source_row.get("aanbod_url") or "").strip()
    if aanbod_url:
        return aanbod_url
    website = (source_row.get("website") or "").strip()
    listing_pattern = (row.get("listing_url_pattern") or "").strip()
    if website and listing_pattern:
        return f"{website.rstrip('/')}{listing_pattern}"
    return website or None


def _dry_run_results(rows: list[dict[str, str]], source_lookup: dict[str, dict[str, str]]) -> list[MiniHarvestResult]:
    results: list[MiniHarvestResult] = []
    for row in rows:
        domain = (row.get("domain") or "").strip().lower()
        strategy = (row.get("discovery_strategy") or "").strip()
        aanbod_url = _resolve_aanbod_url(domain, row, source_lookup) or ""
        results.append(
            summarize_result(
                domain,
                strategy,
                0,
                [],
                f"dry_run aanbod_url={aanbod_url or 'missing'} pattern={(row.get('listing_url_pattern') or '').strip() or '-'}",
            )
        )
    return results


def run(argv: list[str] | None = None) -> dict[str, Path]:
    args = parse_args(argv)
    generated_at = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    census_run_dir = _resolve_census_run(args.census_run)
    census_rows = _read_csv(census_run_dir / "census_inventory.csv")
    discoverable_rows = _discoverable_rows(census_rows)
    source_lookup = _load_source_lookup(_resolve_source_master())

    if args.dry_run:
        results = _dry_run_results(discoverable_rows, source_lookup)
    else:
        settings = load_runtime_settings(load_dotenv_file=False)
        delay_seconds = float(args.delay_seconds if args.delay_seconds is not None else settings.min_request_interval_seconds)
        results = []
        for index, row in enumerate(discoverable_rows):
            domain = (row.get("domain") or "").strip().lower()
            strategy = (row.get("discovery_strategy") or "").strip()
            if index > 0 and delay_seconds > 0:
                time.sleep(delay_seconds)
            results.append(
                harvest_domain_sample(
                    domain,
                    strategy,
                    aanbod_url=_resolve_aanbod_url(domain, row, source_lookup),
                    listing_pattern=(row.get("listing_url_pattern") or "").strip() or None,
                    max_listings=args.max_listings,
                    max_detail_pages=args.max_fichas,
                )
            )

    summary = summarize_run(results, run_id=census_run_dir.name, generated_at=generated_at)
    report_text = generate_markdown_report(summary, results)
    output_dir = DEFAULT_OUTPUT_ROOT / generated_at
    output_paths = write_run_outputs(output_dir, report_text=report_text, results=results)
    print(output_paths["report_md"], flush=True)
    print(output_paths["inventory_csv"], flush=True)
    print(output_paths["samples_csv"], flush=True)
    print(
        (
            f"domains={summary.domains_total} harvest_ok={summary.domains_harvest_ok} blocked={summary.domains_blocked} "
            f"properties={summary.total_properties_extracted} price={format_rate(summary.mean_fill_rate_price)} "
            f"city={format_rate(summary.mean_fill_rate_city)} area={format_rate(summary.mean_fill_rate_area)} "
            f"url={format_rate(summary.mean_fill_rate_url)} verdict={summary.verdict}"
        ),
        flush=True,
    )
    return output_paths


if __name__ == "__main__":
    run()
