from __future__ import annotations

import csv
import shutil
from collections import Counter
from pathlib import Path

from .models import CrawlResult, PropertyCandidate, PropertyInventoryRecord, PropertyRejectedRecord, PropertySource

INVENTORY_FIELDNAMES = [
    "property_id",
    "source_id",
    "source_root_domain",
    "source_aanbod_url",
    "property_url",
    "title",
    "address_raw",
    "city_raw",
    "gemeente",
    "price_raw",
    "price_eur",
    "status",
    "status_raw",
    "living_area_raw",
    "plot_area_raw",
    "rooms_raw",
    "energy_label",
    "image_url",
    "extraction_source",
    "detail_extraction_status",
    "detail_error",
    "first_seen_at",
    "last_seen_at",
    "discovery_run_id",
    "extraction_confidence",
    "address_quality",
    "needs_review",
    "needs_review_reason",
    "review_reason",
]

CANDIDATE_FIELDNAMES = [
    "source_id",
    "root_domain",
    "source_url",
    "property_url",
    "candidate_type",
    "link_text",
    "extraction_method",
    "excluded_reason",
    "is_property_like",
    "property_url_classification",
    "title",
    "address_raw",
    "city_raw",
    "gemeente",
    "price_raw",
    "status_raw",
    "living_area_raw",
    "plot_area_raw",
    "rooms_raw",
    "energy_label",
    "image_url",
    "extraction_source",
    "detail_extraction_status",
    "detail_error",
    "extraction_confidence",
    "address_quality",
    "needs_review",
    "needs_review_reason",
    "review_reason",
]

REJECTED_FIELDNAMES = CANDIDATE_FIELDNAMES + ["rejection_reason"]


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def copy_latest(run_dir: Path, latest_dir: Path, filenames: list[str]) -> None:
    latest_dir.mkdir(parents=True, exist_ok=True)
    for filename in filenames:
        shutil.copy2(run_dir / filename, latest_dir / filename)


def candidate_to_row(candidate: PropertyCandidate) -> dict[str, str]:
    return {
        "source_id": candidate.source_id,
        "root_domain": candidate.root_domain,
        "source_url": candidate.source_url,
        "property_url": candidate.property_url,
        "candidate_type": candidate.candidate_type,
        "link_text": candidate.link_text,
        "extraction_method": candidate.extraction_method,
        "excluded_reason": candidate.excluded_reason,
        "is_property_like": "true" if candidate.is_property_like else "false",
        "property_url_classification": candidate.property_url_classification,
        "title": candidate.title,
        "address_raw": candidate.address_raw,
        "city_raw": candidate.city_raw,
        "gemeente": candidate.gemeente,
        "price_raw": candidate.price_raw,
        "status_raw": candidate.status_raw,
        "living_area_raw": candidate.living_area_raw,
        "plot_area_raw": candidate.plot_area_raw,
        "rooms_raw": candidate.rooms_raw,
        "energy_label": candidate.energy_label,
        "image_url": candidate.image_url,
        "extraction_source": candidate.extraction_source,
        "detail_extraction_status": candidate.detail_extraction_status,
        "detail_error": candidate.detail_error,
        "extraction_confidence": f"{candidate.extraction_confidence:.2f}",
        "address_quality": candidate.address_quality,
        "needs_review": "true" if candidate.needs_review else "false",
        "needs_review_reason": candidate.needs_review_reason,
        "review_reason": candidate.review_reason,
    }


def inventory_to_row(record: PropertyInventoryRecord) -> dict[str, str]:
    return {
        field: getattr(record, field) for field in INVENTORY_FIELDNAMES
    }


def rejected_to_row(record: PropertyRejectedRecord) -> dict[str, str]:
    return {field: getattr(record, field) for field in REJECTED_FIELDNAMES}


def render_report(
    *,
    run_timestamp: str,
    province: str,
    run_status: str,
    started_at: str,
    finished_at: str,
    duration_seconds: float,
    sources_loaded: list[PropertySource],
    crawl_results: list[CrawlResult],
    candidates: list[PropertyCandidate],
    inventory: list[PropertyInventoryRecord],
    rejected: list[PropertyRejectedRecord],
    sources_skipped_invalid_aanbod_url: int = 0,
) -> str:
    succeeded = [result for result in crawl_results if result.ok]
    failed = [result for result in crawl_results if not result.ok]
    timed_out = [result for result in failed if result.timed_out]
    by_status = Counter(record.status for record in inventory)
    by_source = Counter(record.source_id for record in inventory)
    invalid_address_raw_count = sum(1 for record in rejected if record.needs_review_reason == "invalid_address_raw")
    needs_review_count = sum(1 for record in inventory if record.needs_review == "true") + sum(
        1 for record in rejected if record.needs_review == "true"
    )
    clean_available_properties = sum(
        1 for record in inventory if record.status == "beschikbaar" and record.needs_review != "true"
    )
    top_source_lines = [
        f"- {source_id}: {count}"
        for source_id, count in by_source.most_common(10)
    ] or ["- None"]
    failed_lines = [
        f"- {result.source.source_id}: {result.error}"
        for result in failed
    ] or ["- None"]
    error_lines = [
        f"- {result.source.source_id}: {'timeout' if result.timed_out else 'error'} | {result.error}"
        for result in failed
    ] or ["- None"]
    actions = [
        "Review `unknown` status records and expand card heuristics where needed.",
        "Add detail-page extraction for sources with sparse cards or missing address data.",
        "Track `verdwenen` by diffing future inventories against prior runs.",
    ]
    action_lines = [f"- {action}" for action in actions]

    return "\n".join(
        [
            "# Property Discovery Report",
            "",
            f"- Run timestamp: {run_timestamp}",
            f"- Run status: {run_status}",
            f"- Started at: {started_at}",
            f"- Finished at: {finished_at}",
            f"- Duration seconds: {duration_seconds:.1f}",
            f"- Province: {province}",
            f"- Sources total: {len(sources_loaded)}",
            f"- Sources processed: {len(crawl_results)}",
            f"- Sources succeeded: {len(succeeded)}",
            f"- Sources failed: {len(failed)}",
            f"- Sources timeout: {len(timed_out)}",
            f"- Sources skipped invalid aanbod_url: {sources_skipped_invalid_aanbod_url}",
            f"- Properties found: {len(candidates)}",
            f"- Properties matching ready: {len(inventory)}",
            f"- Rejected candidates: {len(rejected)}",
            f"- Invalid address_raw: {invalid_address_raw_count}",
            f"- Needs review: {needs_review_count}",
            f"- Available properties: {by_status.get('beschikbaar', 0)}",
            f"- Clean available properties: {clean_available_properties}",
            f"- Under offer: {by_status.get('onder_bod', 0)}",
            f"- Sold: {by_status.get('verkocht', 0) + by_status.get('verkocht_ov', 0)}",
            f"- Unknown status: {by_status.get('unknown', 0)}",
            "",
            "## Top Sources By Property Count",
            *top_source_lines,
            "",
            "## Failed Sources",
            *failed_lines,
            "",
            "## Errors By Source",
            *error_lines,
            "",
            "## Next Recommended Actions",
            *action_lines,
            "",
        ]
    )
