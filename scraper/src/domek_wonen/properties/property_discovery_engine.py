from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from .listing_page_crawler import ListingPageCrawler
from .models import CrawlResult, PropertyCandidate, PropertyDiscoveryRunOutput, PropertyInventoryRecord
from .property_card_extractor import PropertyCardExtractor
from .property_dedupe import PropertyDedupe, fallback_key, normalize_property_url
from .property_reporter import (
    CANDIDATE_FIELDNAMES,
    INVENTORY_FIELDNAMES,
    candidate_to_row,
    copy_latest,
    inventory_to_row,
    render_report,
    write_csv,
)
from .property_status_classifier import PropertyStatusClassifier, parse_price_eur
from .source_loader import SourceLoader, normalize_province

BASE_DIR = Path(__file__).resolve().parents[4]
DEFAULT_SOURCE_CSV_PATH = BASE_DIR / "data" / "discovery" / "latest" / "makelaar_sources_master.csv"
DEFAULT_RUNS_BASE_DIR = BASE_DIR / "data" / "properties" / "runs"
DEFAULT_LATEST_DIR = BASE_DIR / "data" / "properties" / "latest"


def _property_id(candidate: PropertyCandidate) -> str:
    stable_key = normalize_property_url(candidate.property_url) or fallback_key(candidate)
    digest = hashlib.sha1(stable_key.encode("utf-8")).hexdigest()
    return digest[:16]


def _normalize_candidate(candidate: PropertyCandidate) -> PropertyCandidate:
    property_url = normalize_property_url(candidate.property_url)
    review_reasons: list[str] = []
    if candidate.needs_review and candidate.review_reason:
        review_reasons.append(candidate.review_reason)
    if not property_url:
        review_reasons.append("missing property_url")
    return replace(
        candidate,
        property_url=property_url or candidate.property_url,
        needs_review=bool(review_reasons),
        review_reason="; ".join(dict.fromkeys(reason for reason in review_reasons if reason)),
    )


def _to_inventory_record(
    candidate: PropertyCandidate,
    *,
    run_id: str,
    classifier: PropertyStatusClassifier,
) -> PropertyInventoryRecord:
    status = classifier.classify(candidate.status_raw, candidate.title, candidate.price_raw)
    review_reasons: list[str] = []
    if candidate.needs_review and candidate.review_reason:
        review_reasons.append(candidate.review_reason)
    if status == "unknown":
        review_reasons.append("unknown status")
    if not candidate.address_raw and not candidate.city_raw:
        review_reasons.append("missing address")

    return PropertyInventoryRecord(
        property_id=_property_id(candidate),
        source_id=candidate.source_id,
        source_root_domain=candidate.root_domain,
        source_aanbod_url=candidate.source_url,
        property_url=candidate.property_url,
        title=candidate.title,
        address_raw=candidate.address_raw,
        city_raw=candidate.city_raw,
        gemeente=candidate.gemeente,
        price_raw=candidate.price_raw,
        price_eur=parse_price_eur(candidate.price_raw),
        status=status,
        status_raw=candidate.status_raw,
        living_area_raw=candidate.living_area_raw,
        plot_area_raw=candidate.plot_area_raw,
        rooms_raw=candidate.rooms_raw,
        image_url=candidate.image_url,
        first_seen_at=run_id,
        last_seen_at=run_id,
        discovery_run_id=run_id,
        extraction_confidence=f"{candidate.extraction_confidence:.2f}",
        needs_review="true" if review_reasons else "false",
        review_reason="; ".join(dict.fromkeys(review_reasons)),
    )


def run_property_discovery(
    *,
    province: str,
    max_sources: int,
    max_properties_per_source: int,
    source_csv_path: Path = DEFAULT_SOURCE_CSV_PATH,
    runs_base_dir: Path = DEFAULT_RUNS_BASE_DIR,
    latest_dir: Path = DEFAULT_LATEST_DIR,
    timeout_ms: int = 15000,
) -> PropertyDiscoveryRunOutput:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = runs_base_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    loader = SourceLoader(source_csv_path)
    extractor = PropertyCardExtractor()
    dedupe = PropertyDedupe()
    classifier = PropertyStatusClassifier()

    if max_sources <= 0:
        sources = []
    else:
        sources = loader.load(province=province, max_sources=max_sources)

    crawl_results = []
    candidates: list[PropertyCandidate] = []

    if sources:
        try:
            with ListingPageCrawler(timeout_ms=timeout_ms) as crawler:
                for source in sources:
                    result = crawler.crawl(source)
                    crawl_results.append(result)
                    if not result.ok:
                        continue
                    extracted = extractor.extract(result.html, source, result.final_url)[:max_properties_per_source]
                    candidates.extend(_normalize_candidate(candidate) for candidate in extracted)
        except Exception as exc:
            crawl_results.extend(
                CrawlResult(
                    source=source,
                    ok=False,
                    final_url=source.aanbod_url,
                    error=f"crawler initialization failed: {exc}",
                    elapsed_ms=0,
                )
                for source in sources
            )

    deduped_candidates = dedupe.dedupe(candidates)
    inventory = [_to_inventory_record(candidate, run_id=run_id, classifier=classifier) for candidate in deduped_candidates]

    write_csv(
        run_dir / "property_candidates.csv",
        [candidate_to_row(candidate) for candidate in candidates],
        CANDIDATE_FIELDNAMES,
    )
    write_csv(
        run_dir / "property_inventory.csv",
        [inventory_to_row(record) for record in inventory],
        INVENTORY_FIELDNAMES,
    )
    report_text = render_report(
        run_timestamp=run_id,
        province=normalize_province(province),
        sources_loaded=sources,
        crawl_results=crawl_results,
        candidates=candidates,
        inventory=inventory,
    )
    report_path = run_dir / "property_discovery_report.md"
    report_path.write_text(report_text, encoding="utf-8")

    copy_latest(
        run_dir,
        latest_dir,
        ["property_candidates.csv", "property_inventory.csv", "property_discovery_report.md"],
    )

    return PropertyDiscoveryRunOutput(
        run_id=run_id,
        run_dir=run_dir,
        latest_dir=latest_dir,
        report_path=report_path,
        sources_loaded=len(sources),
        sources_attempted=len(crawl_results),
        sources_succeeded=sum(1 for result in crawl_results if result.ok),
        sources_failed=sum(1 for result in crawl_results if not result.ok),
        total_property_candidates=len(candidates),
        deduped_properties=len(inventory),
    )
