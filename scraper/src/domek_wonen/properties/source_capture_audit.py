from __future__ import annotations

import csv
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from domek_wonen.discovery.discovery_artifacts import resolve_makelaar_sources_master
from domek_wonen.matching.matching_v1 import _is_clean_available, _normalize_property_type, _normalize_text, _safe_int

from .models import CrawlResult, PropertyCandidate, PropertySource
from .property_dedupe import PropertyDedupe
from .property_discovery_engine import BASE_DIR, REPORT_FILENAME
from .property_status_classifier import PropertyStatusClassifier
from .source_loader import SourceLoader
from . import property_discovery_engine as discovery_engine


DEFAULT_OUTPUT_BASE_DIR = BASE_DIR / "data" / "source_capture_audit" / "runs"
DEFAULT_TARGET_AREA_PLATFORM_FINGERPRINT_BASE_DIR = BASE_DIR / "data" / "platform_fingerprint" / "target_area"
DEFAULT_TARGET_GEMEENTES = [
    "Tilburg",
    "Waalwijk",
    "'s-Hertogenbosch",
    "Heusden",
    "Drunen",
    "Nieuwkuijk",
]
DEFAULT_SOURCE_TIMEOUT_SECONDS = 20
DEFAULT_PAGE_TIMEOUT_SECONDS = 15
DEFAULT_DETAIL_TIMEOUT_SECONDS = 6
DEFAULT_MAX_DETAIL_PAGES = 3
DEFAULT_TIMEOUT_MS = 15000
TARGET_PRICE_LIMIT_EUR = 260000

SOURCE_CAPTURE_AUDIT_FIELDNAMES = [
    "source_id",
    "office_name",
    "root_domain",
    "gemeente",
    "detected_platform",
    "parser_status",
    "website_url",
    "aanbod_url",
    "crawl_status",
    "failure_reason",
    "properties_found",
    "matching_ready",
    "clean_available",
    "apartments_total",
    "apartments_lte_260k",
    "apartments_lte_260k_target_area",
    "cheapest_price_eur",
    "cheapest_property_address",
    "cheapest_property_city",
    "cheapest_property_url",
    "recommended_action",
]


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _normalize_gemeente(value: str) -> str:
    return " ".join((value or "").strip().lower().replace("’", "'").split())


def _filter_target_gemeentes(sources: list[PropertySource], target_gemeentes: list[str]) -> list[PropertySource]:
    normalized_targets = {_normalize_gemeente(value) for value in target_gemeentes if value.strip()}
    return [source for source in sources if _normalize_gemeente(source.gemeente) in normalized_targets]


def _resolve_latest_target_area_platform_fingerprint_inventory(
    base_dir: Path = DEFAULT_TARGET_AREA_PLATFORM_FINGERPRINT_BASE_DIR,
) -> Path | None:
    if not base_dir.exists():
        return None
    run_dirs = sorted((path for path in base_dir.iterdir() if path.is_dir()), key=lambda path: path.name, reverse=True)
    for run_dir in run_dirs:
        candidate = run_dir / "target_area_platform_fingerprint_inventory.csv"
        if candidate.exists():
            return candidate
    return None


def _load_platform_metadata(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None or not path.exists():
        return {}

    metadata: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            source_id = (row.get("source_id") or "").strip().lower()
            root_domain = (row.get("root_domain") or "").strip().lower()
            if source_id:
                metadata[f"source_id:{source_id}"] = row
            if root_domain:
                metadata[f"root_domain:{root_domain}"] = row
    return metadata


def _platform_metadata_for_source(source: PropertySource, metadata: dict[str, dict[str, str]]) -> dict[str, str]:
    source_key = f"source_id:{source.source_id.strip().lower()}"
    root_domain_key = f"root_domain:{source.root_domain.strip().lower()}"
    if source_key in metadata:
        return metadata[source_key]
    if root_domain_key in metadata:
        return metadata[root_domain_key]
    return {}


def _is_target_area_city(value: str, target_gemeentes: list[str]) -> bool:
    normalized_value = _normalize_text(value)
    if not normalized_value:
        return False
    normalized_targets = {_normalize_text(item) for item in target_gemeentes if _normalize_text(item)}
    return normalized_value in normalized_targets


def _build_source_row(
    *,
    source: PropertySource,
    crawl_result: CrawlResult,
    candidates: list[PropertyCandidate],
    inventory_rows: list[dict[str, str]],
    target_gemeentes: list[str],
    platform_metadata: dict[str, str],
) -> dict[str, str]:
    clean_available_rows = [row for row in inventory_rows if _is_clean_available(row)]
    apartment_rows = [row for row in inventory_rows if _normalize_property_type(row.get("property_type", "")) == "apartment"]
    apartments_lte_260k_rows = [
        row for row in apartment_rows if (_safe_int(row.get("price_eur")) or 10**12) <= TARGET_PRICE_LIMIT_EUR
    ]
    apartments_lte_260k_target_area_rows = [
        row
        for row in apartments_lte_260k_rows
        if _is_target_area_city(row.get("city_raw", "") or row.get("gemeente", ""), target_gemeentes)
    ]
    cheapest_row: dict[str, str] | None = None
    cheapest_price = 10**12
    for row in inventory_rows:
        price = _safe_int(row.get("price_eur"))
        if price is None or price >= cheapest_price:
            continue
        cheapest_price = price
        cheapest_row = row

    detected_platform = platform_metadata.get("detected_platform", source.detected_platform or "")
    parser_status = platform_metadata.get("parser_status", "supported" if detected_platform == "realworks" else "unknown")
    recommended_action = _recommended_action(
        source=source,
        crawl_result=crawl_result,
        properties_found=len(candidates),
        clean_available=len(clean_available_rows),
        parser_status=parser_status,
    )
    crawl_status = "timeout" if crawl_result.timed_out else ("ok" if crawl_result.ok else "error")

    return {
        "source_id": source.source_id,
        "office_name": source.office_name,
        "root_domain": source.root_domain,
        "gemeente": source.gemeente,
        "detected_platform": detected_platform,
        "parser_status": parser_status,
        "website_url": source.website,
        "aanbod_url": source.aanbod_url,
        "crawl_status": crawl_status,
        "failure_reason": crawl_result.error,
        "properties_found": str(len(candidates)),
        "matching_ready": str(len(inventory_rows)),
        "clean_available": str(len(clean_available_rows)),
        "apartments_total": str(len(apartment_rows)),
        "apartments_lte_260k": str(len(apartments_lte_260k_rows)),
        "apartments_lte_260k_target_area": str(len(apartments_lte_260k_target_area_rows)),
        "cheapest_price_eur": str(cheapest_price) if cheapest_row else "",
        "cheapest_property_address": cheapest_row.get("address_raw", "") if cheapest_row else "",
        "cheapest_property_city": cheapest_row.get("city_raw", "") if cheapest_row else "",
        "cheapest_property_url": cheapest_row.get("property_url", "") if cheapest_row else "",
        "recommended_action": recommended_action,
    }


def _recommended_action(
    *,
    source: PropertySource,
    crawl_result: CrawlResult,
    properties_found: int,
    clean_available: int,
    parser_status: str,
) -> str:
    if parser_status != "supported":
        return "needs_manual_review"
    if crawl_result.timed_out:
        return "parser_supported_but_timeout"
    if properties_found > 0 and clean_available > 0:
        return "working_source"
    if properties_found > 0 and clean_available == 0:
        return "parser_supported_but_no_clean_available"
    if properties_found == 0 and _looks_wrong_realworks_aanbod_url(source.aanbod_url):
        return "parser_supported_but_wrong_aanbod_url"
    if properties_found == 0:
        return "parser_supported_but_no_inventory"
    return "needs_manual_review"


def _looks_wrong_realworks_aanbod_url(aanbod_url: str) -> bool:
    normalized = (aanbod_url or "").strip().casefold()
    return bool(normalized) and "woningaanbod" not in normalized and "aanbod" in normalized


def _inventory_rows_from_candidates(
    *,
    candidates: list[PropertyCandidate],
    run_id: str,
) -> list[dict[str, str]]:
    _accepted_candidates, _rejected_candidates, inventory, _rejected = discovery_engine._build_outputs(
        candidates,
        run_id=run_id,
        dedupe=PropertyDedupe(),
        classifier=PropertyStatusClassifier(),
    )
    return [asdict(row) for row in inventory]


def write_source_capture_audit_inventory(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SOURCE_CAPTURE_AUDIT_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def build_source_capture_audit_report(
    rows: list[dict[str, str]],
    *,
    run_id: str,
    target_gemeentes: list[str],
    platform_filter: str,
    root_domain_filter: str,
) -> str:
    recommended_counts = Counter(row["recommended_action"] for row in rows)
    working_rows = [row for row in rows if row["recommended_action"] == "working_source"]
    kin_rows = [row for row in rows if row["root_domain"].strip().lower() == "kinmakelaars.nl"]

    lines = [
        "# Target Area Source Capture Audit v1",
        "",
        f"- Run timestamp: {run_id}",
        f"- Target gemeentes: {', '.join(target_gemeentes)}",
        f"- Platform filter: {platform_filter or 'all'}",
        f"- Root domain filter: {root_domain_filter or 'all'}",
        f"- Total sources audited: {len(rows)}",
        f"- working_source: {recommended_counts.get('working_source', 0)}",
        f"- parser_supported_but_timeout: {recommended_counts.get('parser_supported_but_timeout', 0)}",
        f"- parser_supported_but_no_inventory: {recommended_counts.get('parser_supported_but_no_inventory', 0)}",
        f"- parser_supported_but_no_clean_available: {recommended_counts.get('parser_supported_but_no_clean_available', 0)}",
        f"- parser_supported_but_wrong_aanbod_url: {recommended_counts.get('parser_supported_but_wrong_aanbod_url', 0)}",
        f"- needs_manual_review: {recommended_counts.get('needs_manual_review', 0)}",
        "",
        "## Top Working Sources",
    ]
    if working_rows:
        sorted_working = sorted(
            working_rows,
            key=lambda row: (
                -int(row["apartments_lte_260k"] or "0"),
                -int(row["clean_available"] or "0"),
                -int(row["properties_found"] or "0"),
                row["root_domain"],
            ),
        )
        for row in sorted_working[:10]:
            lines.append(
                f"- {row['office_name']} ({row['root_domain']} / {row['gemeente']}): "
                f"properties_found={row['properties_found']}, clean_available={row['clean_available']}, "
                f"apartments_lte_260k={row['apartments_lte_260k']}"
            )
    else:
        lines.append("- none")

    lines.extend(["", "## KIN Detail"])
    if kin_rows:
        lines.append(f"- KIN sources audited: {len(kin_rows)}")
        for row in kin_rows:
            lines.append(
                f"- {row['office_name']} ({row['gemeente']}): aanbod_url={row['aanbod_url'] or '-'}, "
                f"properties_found={row['properties_found']}, clean_available={row['clean_available']}, "
                f"apartments_lte_260k={row['apartments_lte_260k']}, failure_reason={row['failure_reason'] or '-'}, "
                f"recommended_action={row['recommended_action']}"
            )
    else:
        lines.append("- KIN sources audited: 0")

    return "\n".join(lines) + "\n"


def write_source_capture_audit_report(
    path: Path,
    rows: list[dict[str, str]],
    *,
    run_id: str,
    target_gemeentes: list[str],
    platform_filter: str,
    root_domain_filter: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        build_source_capture_audit_report(
            rows,
            run_id=run_id,
            target_gemeentes=target_gemeentes,
            platform_filter=platform_filter,
            root_domain_filter=root_domain_filter,
        ),
        encoding="utf-8",
    )


def run_target_area_source_capture_audit(
    *,
    input_path: Path | None = None,
    target_gemeentes: list[str] | None = None,
    platform: str = "",
    root_domain: str = "",
    max_sources: int | None = None,
    max_properties_per_source: int = 20,
    output_base_dir: Path = DEFAULT_OUTPUT_BASE_DIR,
    platform_fingerprint_inventory_path: Path | None = None,
    source_timeout_seconds: int = DEFAULT_SOURCE_TIMEOUT_SECONDS,
    page_timeout_seconds: int = DEFAULT_PAGE_TIMEOUT_SECONDS,
    detail_timeout_seconds: int = DEFAULT_DETAIL_TIMEOUT_SECONDS,
    max_detail_pages: int = DEFAULT_MAX_DETAIL_PAGES,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> tuple[str, list[dict[str, str]], Path, Path]:
    resolved_input_path = resolve_makelaar_sources_master(input_path=input_path, restore_latest=True)
    effective_target_gemeentes = target_gemeentes or list(DEFAULT_TARGET_GEMEENTES)
    resolved_fingerprint_path = (
        platform_fingerprint_inventory_path or _resolve_latest_target_area_platform_fingerprint_inventory()
    )
    platform_metadata = _load_platform_metadata(resolved_fingerprint_path)

    loader = SourceLoader(resolved_input_path)
    sources = loader.load(
        province="Noord-Brabant",
        max_sources=None,
        include_invalid_sources=False,
        platform_filter=platform,
        platform_fingerprint_path=resolved_fingerprint_path,
    )
    sources = _filter_target_gemeentes(sources, effective_target_gemeentes)
    if root_domain.strip():
        normalized_root_domain = root_domain.strip().lower()
        sources = [source for source in sources if source.root_domain.strip().lower() == normalized_root_domain]
    if max_sources is not None:
        sources = sources[:max_sources]

    run_id = _utc_run_id()
    run_dir = output_base_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    inventory_path = run_dir / "source_capture_audit_inventory.csv"
    report_path = run_dir / "source_capture_audit_report.md"

    rows: list[dict[str, str]] = []
    for source in sources:
        crawl_result, candidates = discovery_engine._crawl_source_in_subprocess(
            source=source,
            run_dir=run_dir,
            max_properties_per_source=max_properties_per_source,
            timeout_ms=min(timeout_ms, page_timeout_seconds * 1000),
            page_timeout_seconds=page_timeout_seconds,
            max_detail_pages=max_detail_pages,
            detail_timeout_seconds=detail_timeout_seconds,
            disable_detail_extraction=False,
            disable_platform_parsers=False,
            source_timeout_seconds=source_timeout_seconds,
        )
        inventory_rows = _inventory_rows_from_candidates(candidates=candidates, run_id=run_id)
        rows.append(
            _build_source_row(
                source=source,
                crawl_result=crawl_result,
                candidates=candidates,
                inventory_rows=inventory_rows,
                target_gemeentes=effective_target_gemeentes,
                platform_metadata=_platform_metadata_for_source(source, platform_metadata),
            )
        )

    write_source_capture_audit_inventory(inventory_path, rows)
    write_source_capture_audit_report(
        report_path,
        rows,
        run_id=run_id,
        target_gemeentes=effective_target_gemeentes,
        platform_filter=platform,
        root_domain_filter=root_domain,
    )
    return run_id, rows, inventory_path, report_path
