from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.properties.listing_page_crawler import ListingPageCrawler
from domek_wonen.properties.address_quality import derive_address_from_slug
from domek_wonen.properties.detail_page_extractor import DetailPageExtractor
from domek_wonen.properties.models import PropertyCandidate, PropertySource
from domek_wonen.properties.platform_parser_registry import get_platform_parser
from domek_wonen.properties.property_card_extractor import PropertyCardExtractor
from domek_wonen.properties.property_discovery_engine import _annotate_candidate, _normalize_candidate
from domek_wonen.properties.property_url_classifier import PropertyUrlClassifier


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run PropertyDiscovery for a single source in an isolated process.")
    parser.add_argument("--input", required=True, help="Path to the input source JSON file")
    parser.add_argument("--output", required=True, help="Path to the output result JSON file")
    return parser.parse_args(argv)


def _write_output(output_path: Path, payload: dict[str, object]) -> None:
    output_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _build_source(payload: dict[str, object]) -> PropertySource:
    return PropertySource(
        source_id=str(payload.get("source_id") or payload.get("root_domain") or payload.get("office_name") or "source"),
        office_name=str(payload.get("office_name") or ""),
        root_domain=str(payload.get("root_domain") or ""),
        website=str(payload.get("website") or ""),
        aanbod_url=str(payload.get("aanbod_url") or ""),
        gemeente=str(payload.get("gemeente") or ""),
        province=str(payload.get("province") or ""),
        legal_status="allowed_official_source",
        aanbod_url_quality="valid",
        is_active=True,
        source_origin=str(payload.get("source_origin") or ""),
        detected_platform=str(payload.get("detected_platform") or ""),
    )


def _serialize_candidates(candidates: list[PropertyCandidate], *, accepted: bool) -> list[dict[str, object]]:
    serialized: list[dict[str, object]] = []
    for candidate in candidates:
        is_accepted = candidate.property_url_classification == "property_detail_candidate"
        if is_accepted == accepted:
            serialized.append(asdict(candidate))
    return serialized


def _with_detail_status(candidate: PropertyCandidate, *, status: str) -> PropertyCandidate:
    return PropertyCandidate(
        source_id=candidate.source_id,
        source_url=candidate.source_url,
        root_domain=candidate.root_domain,
        gemeente=candidate.gemeente,
        property_url=candidate.property_url,
        candidate_type=candidate.candidate_type,
        link_text=candidate.link_text,
        extraction_method=candidate.extraction_method,
        excluded_reason=candidate.excluded_reason,
        is_property_like=candidate.is_property_like,
        property_url_classification=candidate.property_url_classification,
        title=candidate.title,
        address_raw=candidate.address_raw,
        city_raw=candidate.city_raw,
        price_raw=candidate.price_raw,
        status_raw=candidate.status_raw,
        living_area_raw=candidate.living_area_raw,
        plot_area_raw=candidate.plot_area_raw,
        rooms_raw=candidate.rooms_raw,
        energy_label=candidate.energy_label,
        image_url=candidate.image_url,
        extraction_source=candidate.extraction_source,
        detail_extraction_status=status,
        detail_error="",
        extraction_confidence=candidate.extraction_confidence,
        address_quality=candidate.address_quality,
        needs_review=candidate.needs_review,
        needs_review_reason=candidate.needs_review_reason,
        review_reason=candidate.review_reason,
    )


def _prepare_base_candidates(
    candidates: list[PropertyCandidate],
    *,
    max_detail_pages: int,
    disable_detail_extraction: bool,
) -> list[PropertyCandidate]:
    prepared: list[PropertyCandidate] = []
    pending_budget = 0
    for candidate in candidates:
        if disable_detail_extraction or not _needs_detail_enrichment(candidate):
            status = "skipped"
        elif pending_budget < max_detail_pages:
            status = "pending"
            pending_budget += 1
        else:
            status = "skipped"
        prepared.append(_with_detail_status(candidate, status=status))
    return prepared


def _needs_detail_enrichment(candidate: PropertyCandidate) -> bool:
    if not candidate.property_url:
        return False
    if not (candidate.address_raw or "").strip():
        return True
    if not (candidate.price_raw or "").strip():
        return True
    return False


def _finalize_candidate(candidate: PropertyCandidate) -> PropertyCandidate:
    review_reasons: list[str] = []
    if candidate.needs_review and candidate.review_reason:
        review_reasons.append(candidate.review_reason)
    if not (candidate.address_raw or "").strip() and not (candidate.city_raw or "").strip():
        review_reasons.append("missing address after detail extraction")
    return PropertyCandidate(
        source_id=candidate.source_id,
        source_url=candidate.source_url,
        root_domain=candidate.root_domain,
        gemeente=candidate.gemeente,
        property_url=candidate.property_url,
        candidate_type=candidate.candidate_type,
        link_text=candidate.link_text,
        extraction_method=candidate.extraction_method,
        excluded_reason=candidate.excluded_reason,
        is_property_like=candidate.is_property_like,
        property_url_classification=candidate.property_url_classification,
        title=candidate.title,
        address_raw=candidate.address_raw,
        city_raw=candidate.city_raw,
        price_raw=candidate.price_raw,
        status_raw=candidate.status_raw,
        living_area_raw=candidate.living_area_raw,
        plot_area_raw=candidate.plot_area_raw,
        rooms_raw=candidate.rooms_raw,
        energy_label=candidate.energy_label,
        image_url=candidate.image_url,
        extraction_source=candidate.extraction_source,
        detail_extraction_status=candidate.detail_extraction_status,
        detail_error=candidate.detail_error,
        extraction_confidence=candidate.extraction_confidence,
        address_quality=candidate.address_quality,
        needs_review=bool(review_reasons),
        needs_review_reason=candidate.needs_review_reason,
        review_reason="; ".join(dict.fromkeys(review_reasons)),
    )


def _enrich_candidates(
    crawler: ListingPageCrawler,
    candidates: list[PropertyCandidate],
    source: PropertySource,
    *,
    max_detail_pages: int,
    detail_timeout_seconds: int,
    disable_detail_extraction: bool,
) -> list[PropertyCandidate]:
    extractor = DetailPageExtractor()
    enriched: list[PropertyCandidate] = []
    detail_budget = 0
    for candidate in candidates:
        should_enrich = not disable_detail_extraction and _needs_detail_enrichment(candidate) and detail_budget < max_detail_pages
        current = _with_detail_status(candidate, status="pending" if should_enrich else "skipped")
        if should_enrich:
            detail_budget += 1
            try:
                detail_result = crawler.fetch(
                    candidate.property_url,
                    source,
                    timeout_ms=max(1, detail_timeout_seconds) * 1000,
                )
                if detail_result.ok:
                    current = extractor.enrich(current, detail_result.html, detail_result.final_url)
                else:
                    slug_address, slug_city = derive_address_from_slug(candidate.property_url)
                    current = PropertyCandidate(
                        source_id=candidate.source_id,
                        source_url=candidate.source_url,
                        root_domain=candidate.root_domain,
                        gemeente=candidate.gemeente,
                        property_url=candidate.property_url,
                        candidate_type=candidate.candidate_type,
                        link_text=candidate.link_text,
                        extraction_method=candidate.extraction_method,
                        excluded_reason=candidate.excluded_reason,
                        is_property_like=candidate.is_property_like,
                        property_url_classification=candidate.property_url_classification,
                        title=candidate.title,
                        address_raw=slug_address or candidate.address_raw,
                        city_raw=slug_city or candidate.city_raw,
                        price_raw=candidate.price_raw,
                        status_raw=candidate.status_raw,
                        living_area_raw=candidate.living_area_raw,
                        plot_area_raw=candidate.plot_area_raw,
                        rooms_raw=candidate.rooms_raw,
                        energy_label=candidate.energy_label,
                        image_url=candidate.image_url,
                        extraction_source="url_slug" if slug_address else current.extraction_source,
                        detail_extraction_status="failed",
                        detail_error=detail_result.error or "detail page fetch failed",
                        extraction_confidence=candidate.extraction_confidence,
                        address_quality=candidate.address_quality,
                        needs_review=candidate.needs_review,
                        needs_review_reason=candidate.needs_review_reason,
                        review_reason=candidate.review_reason,
                    )
            except Exception as exc:
                slug_address, slug_city = derive_address_from_slug(candidate.property_url)
                current = PropertyCandidate(
                    source_id=candidate.source_id,
                    source_url=candidate.source_url,
                    root_domain=candidate.root_domain,
                    gemeente=candidate.gemeente,
                    property_url=candidate.property_url,
                    candidate_type=candidate.candidate_type,
                    link_text=candidate.link_text,
                    extraction_method=candidate.extraction_method,
                    excluded_reason=candidate.excluded_reason,
                    is_property_like=candidate.is_property_like,
                    property_url_classification=candidate.property_url_classification,
                    title=candidate.title,
                    address_raw=slug_address or candidate.address_raw,
                    city_raw=slug_city or candidate.city_raw,
                    price_raw=candidate.price_raw,
                    status_raw=candidate.status_raw,
                    living_area_raw=candidate.living_area_raw,
                    plot_area_raw=candidate.plot_area_raw,
                    rooms_raw=candidate.rooms_raw,
                    energy_label=candidate.energy_label,
                    image_url=candidate.image_url,
                    extraction_source="url_slug" if slug_address else current.extraction_source,
                    detail_extraction_status="failed",
                    detail_error=str(exc),
                    extraction_confidence=candidate.extraction_confidence,
                    address_quality=candidate.address_quality,
                    needs_review=candidate.needs_review,
                    needs_review_reason=candidate.needs_review_reason,
                    review_reason=candidate.review_reason,
                )
        enriched.append(_finalize_candidate(current))
    return enriched


def run_worker(input_path: Path, output_path: Path) -> int:
    started = time.perf_counter()
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    source = _build_source(payload)
    extractor = PropertyCardExtractor()
    url_classifier = PropertyUrlClassifier()
    timeout_ms = int(payload.get("timeout_ms") or 30000)
    page_timeout_seconds = int(payload.get("page_timeout_seconds") or 30)
    effective_timeout_ms = min(timeout_ms, page_timeout_seconds * 1000)
    max_properties_per_source = int(payload.get("max_properties_per_source") or 50)
    max_detail_pages = int(payload.get("max_detail_pages") or 3)
    detail_timeout_seconds = int(payload.get("detail_timeout_seconds") or 10)
    disable_detail_extraction = bool(payload.get("disable_detail_extraction") or False)
    disable_platform_parsers = bool(payload.get("disable_platform_parsers") or False)
    detected_platform = (source.detected_platform or "").strip().lower()

    output: dict[str, object] = {
        "status": "failed",
        "properties": [],
        "rejected": [],
        "errors": [],
        "duration_seconds": 0.0,
        "parser_info": {
            "parser_used": "",
            "realworks_parser_success": False,
            "realworks_parser_failed": False,
            "parser_fallback_used": False,
            "generic_parser_success": False,
        },
    }

    try:
        if not disable_platform_parsers and detected_platform:
            platform_parser = get_platform_parser(detected_platform)
            if platform_parser is not None:
                try:
                    parsed_candidates = platform_parser.parse(
                        source,
                        max_properties_per_source=max_properties_per_source,
                        page_timeout_seconds=page_timeout_seconds,
                    )
                    parsed_candidates = [
                        _finalize_candidate(_annotate_candidate(_normalize_candidate(candidate), url_classifier))
                        for candidate in parsed_candidates
                    ]
                    if parsed_candidates:
                        output["status"] = "succeeded"
                        output["properties"] = _serialize_candidates(parsed_candidates, accepted=True)
                        output["rejected"] = _serialize_candidates(parsed_candidates, accepted=False)
                        output["errors"] = []
                        output["parser_info"] = {
                            "parser_used": f"{detected_platform}_parser",
                            "realworks_parser_success": detected_platform == "realworks",
                            "realworks_parser_failed": False,
                            "parser_fallback_used": False,
                            "generic_parser_success": False,
                        }
                        return_code = 0
                        return return_code
                    raise RuntimeError(f"{detected_platform} parser returned no candidates")
                except Exception as exc:
                    output["errors"] = [str(exc)]
                    output["parser_info"] = {
                        "parser_used": "",
                        "realworks_parser_success": False,
                        "realworks_parser_failed": detected_platform == "realworks",
                        "parser_fallback_used": True,
                        "generic_parser_success": False,
                    }

        with ListingPageCrawler(timeout_ms=effective_timeout_ms) as crawler:
            result = crawler.crawl(source)
            if not result.ok:
                output["errors"] = [result.error or "crawl failed"]
                return_code = 1
            else:
                raw_candidates = extractor.extract(result.html, source, result.final_url)[:max_properties_per_source]
                annotated = [_annotate_candidate(_normalize_candidate(candidate), url_classifier) for candidate in raw_candidates]
                base_candidates = _prepare_base_candidates(
                    annotated,
                    max_detail_pages=max_detail_pages,
                    disable_detail_extraction=disable_detail_extraction,
                )
                output["status"] = "partial"
                output["properties"] = _serialize_candidates(base_candidates, accepted=True)
                output["rejected"] = _serialize_candidates(base_candidates, accepted=False)
                output["errors"] = []
                output["duration_seconds"] = round(time.perf_counter() - started, 3)
                _write_output(output_path, output)

                annotated = _enrich_candidates(
                    crawler,
                    annotated,
                    source,
                    max_detail_pages=max_detail_pages,
                    detail_timeout_seconds=detail_timeout_seconds,
                    disable_detail_extraction=disable_detail_extraction,
                )
                output["status"] = "succeeded"
                output["properties"] = _serialize_candidates(annotated, accepted=True)
                output["rejected"] = _serialize_candidates(annotated, accepted=False)
                output["parser_info"] = {
                    "parser_used": "generic",
                    "realworks_parser_success": False,
                    "realworks_parser_failed": bool(output["parser_info"].get("realworks_parser_failed")),
                    "parser_fallback_used": bool(output["parser_info"].get("parser_fallback_used")),
                    "generic_parser_success": True,
                }
                return_code = 0
    except Exception as exc:
        if output["properties"] or output["rejected"]:
            output["status"] = "partial"
        else:
            output["status"] = "failed"
        output["errors"] = [str(exc)]
        return_code = 1
    finally:
        output["duration_seconds"] = round(time.perf_counter() - started, 3)
        _write_output(output_path, output)

    return return_code


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run_worker(Path(args.input), Path(args.output))


if __name__ == "__main__":
    raise SystemExit(main())
