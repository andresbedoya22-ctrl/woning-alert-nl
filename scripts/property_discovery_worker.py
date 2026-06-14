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
from domek_wonen.properties.models import PropertyCandidate, PropertySource
from domek_wonen.properties.property_card_extractor import PropertyCardExtractor
from domek_wonen.properties.property_discovery_engine import _annotate_candidate, _normalize_candidate
from domek_wonen.properties.property_url_classifier import PropertyUrlClassifier


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run PropertyDiscovery for a single source in an isolated process.")
    parser.add_argument("--input", required=True, help="Path to the input source JSON file")
    parser.add_argument("--output", required=True, help="Path to the output result JSON file")
    return parser.parse_args(argv)


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
    )


def _serialize_candidates(candidates: list[PropertyCandidate], *, accepted: bool) -> list[dict[str, object]]:
    serialized: list[dict[str, object]] = []
    for candidate in candidates:
        is_accepted = candidate.property_url_classification == "property_detail_candidate"
        if is_accepted == accepted:
            serialized.append(asdict(candidate))
    return serialized


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

    output: dict[str, object] = {
        "status": "failed",
        "properties": [],
        "rejected": [],
        "errors": [],
        "duration_seconds": 0.0,
    }

    try:
        with ListingPageCrawler(timeout_ms=effective_timeout_ms) as crawler:
            result = crawler.crawl(source)
            if not result.ok:
                output["errors"] = [result.error or "crawl failed"]
                return_code = 1
            else:
                raw_candidates = extractor.extract(result.html, source, result.final_url)[:max_properties_per_source]
                annotated = [_annotate_candidate(_normalize_candidate(candidate), url_classifier) for candidate in raw_candidates]
                output["status"] = "succeeded"
                output["properties"] = _serialize_candidates(annotated, accepted=True)
                output["rejected"] = _serialize_candidates(annotated, accepted=False)
                return_code = 0
    except Exception as exc:
        output["errors"] = [str(exc)]
        return_code = 1
    finally:
        output["duration_seconds"] = round(time.perf_counter() - started, 3)
        output_path.write_text(json.dumps(output, ensure_ascii=True, indent=2), encoding="utf-8")

    return return_code


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run_worker(Path(args.input), Path(args.output))


if __name__ == "__main__":
    raise SystemExit(main())
