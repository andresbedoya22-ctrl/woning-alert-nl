from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import fields, replace
from datetime import datetime, timezone
from pathlib import Path

from .address_quality import classify_address_quality, derive_address_from_slug
from .models import (
    CrawlResult,
    PropertyCandidate,
    PropertyDiscoveryRunOutput,
    PropertyInventoryRecord,
    PropertyRejectedRecord,
    PropertySource,
)
from .property_dedupe import PropertyDedupe, fallback_key, normalize_property_url
from .property_reporter import (
    CANDIDATE_FIELDNAMES,
    INVENTORY_FIELDNAMES,
    REJECTED_FIELDNAMES,
    candidate_to_row,
    copy_latest,
    inventory_to_row,
    rejected_to_row,
    render_report,
    write_csv,
)
from .property_status_classifier import PropertyStatusClassifier, parse_price_eur
from .property_url_classifier import PropertyUrlClassifier
from .source_loader import MissingSourceFileError, SourceLoader, normalize_province

BASE_DIR = Path(__file__).resolve().parents[4]
DEFAULT_SOURCE_CSV_PATH = BASE_DIR / "data" / "discovery" / "latest" / "makelaar_sources_master.csv"
DEFAULT_PLATFORM_FINGERPRINT_INPUT = (
    BASE_DIR / "data" / "discovery" / "platform_fingerprint" / "platform_fingerprint_results.csv"
)
DEFAULT_RUNS_BASE_DIR = BASE_DIR / "data" / "property_discovery" / "runs"
DEFAULT_LATEST_DIR = BASE_DIR / "data" / "property_discovery" / "latest"
LEGACY_INVENTORY_FILENAME = "property_inventory.csv"
LEGACY_REJECTED_FILENAME = "property_rejected.csv"
INVENTORY_FILENAME = "matching_ready_inventory.csv"
REJECTED_FILENAME = "rejected_property_candidates.csv"
REPORT_FILENAME = "property_discovery_run_report.md"
_PROPERTY_CANDIDATE_FIELDS = {field.name for field in fields(PropertyCandidate)}
_WORKER_SCRIPT_PATH = BASE_DIR / "scripts" / "property_discovery_worker.py"


def _log(message: str) -> None:
    print(f"[property-discovery] {message}", flush=True)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_timestamp(value: datetime) -> str:
    return value.strftime("%Y%m%dT%H%M%SZ")


def _create_run_dir(base_dir: Path, run_timestamp: str) -> tuple[str, Path]:
    run_id = run_timestamp
    run_dir = base_dir / run_id
    suffix = 1
    while run_dir.exists():
        run_id = f"{run_timestamp}-{suffix:02d}"
        run_dir = base_dir / run_id
        suffix += 1
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_id, run_dir


def _relative_windows_path(path: Path) -> str:
    try:
        relative = path.resolve().relative_to(BASE_DIR.resolve())
        return str(relative).replace("/", "\\")
    except ValueError:
        return str(path)


def _recommended_build_command(source_csv_path: Path) -> str:
    discovered_path = source_csv_path.parent / "discovered_sources.csv"
    return (
        "py -3.12 scripts\\build_source_master.py "
        f"--input {_relative_windows_path(discovered_path)} "
        f"--output {_relative_windows_path(source_csv_path)}"
    )


def restore_latest_discovery_if_missing(source_csv_path: Path) -> bool:
    if source_csv_path.exists():
        return False

    latest_dir = source_csv_path.parent
    runs_dir = latest_dir.parent / "runs"
    if not runs_dir.exists():
        return False

    valid_runs: list[Path] = []
    for candidate in runs_dir.iterdir():
        if not candidate.is_dir():
            continue
        if (candidate / "makelaar_sources_master.csv").exists() and (candidate / "discovered_sources.csv").exists():
            valid_runs.append(candidate)

    if not valid_runs:
        return False

    latest_dir.mkdir(parents=True, exist_ok=True)
    selected_run = sorted(valid_runs, key=lambda path: path.name, reverse=True)[0]
    for item in selected_run.iterdir():
        destination = latest_dir / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)

    _log(f"restored discovery latest from run {selected_run.name}")
    return True


def _write_missing_sources_report(
    *,
    report_path: Path,
    run_id: str,
    province: str,
    started_at: datetime,
    finished_at: datetime,
    missing_path: Path,
) -> None:
    report_text = "\n".join(
        [
            "# Property Discovery Report",
            "",
            f"- Run timestamp: {run_id}",
            "- Run status: failed_missing_sources",
            f"- Started at: {started_at.isoformat()}",
            f"- Finished at: {finished_at.isoformat()}",
            f"- Duration seconds: {max((finished_at - started_at).total_seconds(), 0.0):.1f}",
            f"- Province: {normalize_province(province)}",
            "- Sources total: 0",
            "- Sources processed: 0",
            "- Sources succeeded: 0",
            "- Sources failed: 0",
            "- Sources timeout: 0",
            "- Sources skipped invalid aanbod_url: 0",
            "- Properties found: 0",
            "- Properties matching ready: 0",
            "- Rejected candidates: 0",
            "",
            "## Failure",
            f"- Missing source file: {_relative_windows_path(missing_path)}",
            f"- Recommended command: `{_recommended_build_command(missing_path)}`",
            "",
        ]
    )
    report_path.write_text(report_text, encoding="utf-8")


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
        needs_review_reason=candidate.needs_review_reason,
        review_reason="; ".join(dict.fromkeys(reason for reason in review_reasons if reason)),
    )


def _unique_reasons(*reason_groups: list[str]) -> str:
    reasons: list[str] = []
    for group in reason_groups:
        reasons.extend(reason for reason in group if reason)
    return "; ".join(dict.fromkeys(reasons))


_CITY_LOWERCASE_PARTICLES = {"aan", "de", "den", "der", "het", "op", "te", "ten", "ter", "van"}
_INVALID_PRICE_PATTERNS = (
    " per ",
    " per maand",
    "/m²",
    "/m2",
    "m²",
    "m2",
    "servicekosten",
    "huur",
)


def _format_place_token(token: str, *, lowercase_particles: set[str], is_first: bool) -> str:
    lowered = token.casefold()
    if lowered == "'s":
        return "'s"
    if lowered in lowercase_particles and not is_first:
        return lowered
    return token[:1].upper() + token[1:].lower()


def _normalize_city_raw(city_raw: str) -> str:
    value = re.sub(r"\s+", " ", (city_raw or "").strip())
    if not value:
        return ""
    value = re.sub(r"(?i)^in\s+", "", value).strip()
    if not value:
        return ""

    parts = [segment for segment in re.split(r"([ -])", value) if segment]
    formatted: list[str] = []
    word_index = 0
    for part in parts:
        if part in {" ", "-"}:
            formatted.append(part)
            continue
        formatted.append(
            _format_place_token(part, lowercase_particles=_CITY_LOWERCASE_PARTICLES, is_first=(word_index == 0))
        )
        word_index += 1
    return "".join(formatted)


def _is_valid_city_raw(city_raw: str) -> bool:
    normalized = _normalize_city_raw(city_raw)
    if not normalized:
        return False
    collapsed = re.sub(r"[^A-Za-zÀ-ÿ']", "", normalized)
    if len(collapsed) <= 1:
        return False
    if normalized.isnumeric():
        return False
    return True


def _select_needs_review_reason(current: str, *candidates: str) -> str:
    if current:
        return current
    for candidate in candidates:
        if candidate:
            return candidate
    return ""


def _is_valid_price(price_raw: str, price_eur: str) -> bool:
    normalized_price_raw = f" {(price_raw or '').strip().casefold()} "
    if any(pattern in normalized_price_raw for pattern in _INVALID_PRICE_PATTERNS):
        return False
    if not price_eur.isdigit():
        return False
    if int(price_eur) < 100000:
        return False
    if not (price_raw or "").strip():
        return False
    return True


def _apply_address_quality_gate(candidate: PropertyCandidate) -> PropertyCandidate:
    review_reasons = [candidate.review_reason] if candidate.review_reason else []
    address_raw = (candidate.address_raw or "").strip()
    city_raw = (candidate.city_raw or "").strip()
    property_url = candidate.property_url or ""
    address_quality = classify_address_quality(address_raw, property_url)
    extraction_source = candidate.extraction_source

    if address_quality in {"weak", "invalid"}:
        slug_address, slug_city = derive_address_from_slug(property_url)
        if slug_address:
            address_raw = slug_address
            city_raw = city_raw or slug_city
            extraction_source = "url_slug"
            address_quality = classify_address_quality(address_raw, property_url)

    needs_review = candidate.needs_review
    needs_review_reason = candidate.needs_review_reason
    city_raw = _normalize_city_raw(city_raw)
    if address_quality != "valid":
        if not address_raw and not city_raw:
            if candidate.detail_extraction_status == "failed":
                review_reasons.append("missing address after detail extraction")
            else:
                review_reasons.append("missing address")
        needs_review = True
        needs_review_reason = _select_needs_review_reason(needs_review_reason, "invalid_address_raw")
        review_reasons.append("invalid address_raw after quality gate")
    if not _is_valid_city_raw(city_raw):
        needs_review = True
        needs_review_reason = _select_needs_review_reason(needs_review_reason, "invalid_city_raw")
        review_reasons.append("invalid city_raw after quality gate")

    return replace(
        candidate,
        address_raw=address_raw,
        city_raw=city_raw,
        extraction_source=extraction_source,
        address_quality=address_quality,
        needs_review=needs_review,
        needs_review_reason=needs_review_reason,
        review_reason=_unique_reasons(review_reasons),
    )


def _to_rejected_record(candidate: PropertyCandidate) -> PropertyRejectedRecord:
    rejection_reason = candidate.needs_review_reason or candidate.excluded_reason or candidate.review_reason
    if not rejection_reason and candidate.property_url_classification not in {"", "other"}:
        rejection_reason = candidate.property_url_classification
    return PropertyRejectedRecord(
        source_id=candidate.source_id,
        root_domain=candidate.root_domain,
        source_url=candidate.source_url,
        property_url=candidate.property_url,
        title=candidate.title,
        address_raw=candidate.address_raw,
        city_raw=candidate.city_raw,
        gemeente=candidate.gemeente,
        price_raw=candidate.price_raw,
        status_raw=candidate.status_raw,
        living_area_raw=candidate.living_area_raw,
        plot_area_raw=candidate.plot_area_raw,
        rooms_raw=candidate.rooms_raw,
        rooms_count=candidate.rooms_count,
        bedrooms_count=candidate.bedrooms_count,
        living_area_m2=candidate.living_area_m2,
        property_type=candidate.property_type,
        energy_label=candidate.energy_label,
        has_garden=candidate.has_garden,
        has_balcony=candidate.has_balcony,
        image_url=candidate.image_url,
        rejection_reason=rejection_reason,
        extraction_source=candidate.extraction_source,
        detail_extraction_status=candidate.detail_extraction_status,
        detail_error=candidate.detail_error,
        extraction_confidence=f"{candidate.extraction_confidence:.2f}",
        address_quality=candidate.address_quality,
        needs_review="true" if candidate.needs_review else "false",
        needs_review_reason=candidate.needs_review_reason,
        review_reason=candidate.review_reason,
        candidate_type=candidate.candidate_type,
        link_text=candidate.link_text,
        extraction_method=candidate.extraction_method,
        excluded_reason=candidate.excluded_reason,
        is_property_like="true" if candidate.is_property_like else "false",
        property_url_classification=candidate.property_url_classification,
    )


def _annotate_candidate(candidate: PropertyCandidate, url_classifier: PropertyUrlClassifier) -> PropertyCandidate:
    classification = url_classifier.classify(candidate.property_url, candidate.root_domain)
    review_reasons = [candidate.review_reason] if candidate.review_reason else []
    if classification.excluded_reason:
        review_reasons.append(classification.excluded_reason)
    return replace(
        candidate,
        excluded_reason=classification.excluded_reason,
        is_property_like=classification.is_property_like,
        property_url_classification=classification.classification,
        address_quality=candidate.address_quality,
        needs_review=bool(candidate.needs_review or review_reasons),
        needs_review_reason=candidate.needs_review_reason,
        review_reason="; ".join(dict.fromkeys(reason for reason in review_reasons if reason)),
    )


def _to_inventory_record(
    candidate: PropertyCandidate,
    *,
    run_id: str,
    classifier: PropertyStatusClassifier,
) -> PropertyInventoryRecord:
    status = classifier.classify(candidate.status_raw, candidate.title, candidate.price_raw)
    price_eur = parse_price_eur(candidate.price_raw)
    review_reasons: list[str] = []
    needs_review_reason = candidate.needs_review_reason
    if candidate.needs_review and candidate.review_reason:
        review_reasons.append(candidate.review_reason)
    if not _is_valid_price(candidate.price_raw, price_eur):
        review_reasons.append("invalid price")
        needs_review_reason = _select_needs_review_reason(needs_review_reason, "invalid_price")
    if status == "unknown":
        review_reasons.append("unknown status")
        needs_review_reason = _select_needs_review_reason(needs_review_reason, "unknown_status")
    if not candidate.address_raw and not candidate.city_raw:
        if candidate.detail_extraction_status == "failed":
            review_reasons.append("missing address after detail extraction")
        else:
            review_reasons.append("missing address")
    if not _is_valid_city_raw(candidate.city_raw):
        review_reasons.append("invalid city_raw")
        needs_review_reason = _select_needs_review_reason(needs_review_reason, "invalid_city_raw")
    if candidate.extraction_source != "realworks_parser":
        fallback_clean = (
            candidate.address_quality == "valid"
            and _is_valid_city_raw(candidate.city_raw)
            and _is_valid_price(candidate.price_raw, price_eur)
            and status == "beschikbaar"
        )
        if not fallback_clean:
            review_reasons.append("fallback extraction requires valid address, city, price, and beschikbaar status")

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
        price_eur=price_eur,
        status=status,
        status_raw=candidate.status_raw,
        living_area_raw=candidate.living_area_raw,
        plot_area_raw=candidate.plot_area_raw,
        rooms_raw=candidate.rooms_raw,
        rooms_count=candidate.rooms_count,
        bedrooms_count=candidate.bedrooms_count,
        living_area_m2=candidate.living_area_m2,
        property_type=candidate.property_type,
        energy_label=candidate.energy_label,
        has_garden=candidate.has_garden,
        has_balcony=candidate.has_balcony,
        image_url=candidate.image_url,
        extraction_source=candidate.extraction_source,
        detail_extraction_status=candidate.detail_extraction_status,
        detail_error=candidate.detail_error,
        first_seen_at=run_id,
        last_seen_at=run_id,
        discovery_run_id=run_id,
        extraction_confidence=f"{candidate.extraction_confidence:.2f}",
        address_quality=candidate.address_quality,
        needs_review="true" if review_reasons else "false",
        needs_review_reason=needs_review_reason if review_reasons else "",
        review_reason="; ".join(dict.fromkeys(review_reasons)),
    )


def _build_outputs(
    candidates: list[PropertyCandidate],
    *,
    run_id: str,
    dedupe: PropertyDedupe,
    classifier: PropertyStatusClassifier,
) -> tuple[list[PropertyCandidate], list[PropertyCandidate], list[PropertyInventoryRecord], list[PropertyRejectedRecord]]:
    deduped_candidates = [_apply_address_quality_gate(candidate) for candidate in dedupe.dedupe(candidates)]
    accepted_candidates: list[PropertyCandidate] = []
    rejected_candidates: list[PropertyCandidate] = []

    for candidate in deduped_candidates:
        if candidate.property_url_classification == "property_detail_candidate" and candidate.address_quality == "valid":
            accepted_candidates.append(candidate)
        else:
            rejected_candidates.append(candidate)

    inventory = [_to_inventory_record(candidate, run_id=run_id, classifier=classifier) for candidate in accepted_candidates]
    rejected = [_to_rejected_record(candidate) for candidate in rejected_candidates]
    return accepted_candidates, rejected_candidates, inventory, rejected


def _write_checkpoint(
    *,
    run_dir: Path,
    report_path: Path,
    run_id: str,
    province: str,
    run_status: str,
    started_at: datetime,
    finished_at: datetime,
    sources: list[PropertySource],
    crawl_results: list[CrawlResult],
    candidates: list[PropertyCandidate],
    inventory: list[PropertyInventoryRecord],
    rejected: list[PropertyRejectedRecord],
    sources_skipped_invalid_aanbod_url: int = 0,
) -> None:
    candidate_rows = [candidate_to_row(candidate) for candidate in candidates]
    inventory_rows = [inventory_to_row(record) for record in inventory]
    rejected_rows = [
        rejected_to_row(record)
        for record in rejected
        if any(
            (
                (record.property_url or "").strip(),
                (record.address_raw or "").strip(),
                (record.city_raw or "").strip(),
                (record.price_raw or "").strip(),
                (record.status_raw or "").strip(),
            )
        )
    ]

    write_csv(run_dir / "property_candidates.csv", candidate_rows, CANDIDATE_FIELDNAMES)
    write_csv(run_dir / INVENTORY_FILENAME, inventory_rows, INVENTORY_FIELDNAMES)
    write_csv(run_dir / LEGACY_INVENTORY_FILENAME, inventory_rows, INVENTORY_FIELDNAMES)
    write_csv(run_dir / REJECTED_FILENAME, rejected_rows, REJECTED_FIELDNAMES)
    write_csv(run_dir / LEGACY_REJECTED_FILENAME, rejected_rows, REJECTED_FIELDNAMES)

    report_text = render_report(
        run_timestamp=run_id,
        province=normalize_province(province),
        run_status=run_status,
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat(),
        duration_seconds=max((finished_at - started_at).total_seconds(), 0.0),
        sources_loaded=sources,
        crawl_results=crawl_results,
        candidates=candidates,
        inventory=inventory,
        rejected=rejected,
        sources_skipped_invalid_aanbod_url=sources_skipped_invalid_aanbod_url,
    )
    report_path.write_text(report_text, encoding="utf-8")


def _deserialize_candidate(payload: dict[str, object]) -> PropertyCandidate:
    normalized = {field_name: payload.get(field_name) for field_name in _PROPERTY_CANDIDATE_FIELDS}
    return PropertyCandidate(**normalized)


def _parser_info_from_payload(payload: dict[str, object]) -> dict[str, bool | str]:
    parser_info = payload.get("parser_info")
    if not isinstance(parser_info, dict):
        parser_info = {}
    return {
        "parser_used": str(parser_info.get("parser_used") or ""),
        "realworks_parser_success": bool(parser_info.get("realworks_parser_success") or False),
        "realworks_parser_failed": bool(parser_info.get("realworks_parser_failed") or False),
        "parser_fallback_used": bool(parser_info.get("parser_fallback_used") or False),
        "generic_parser_success": bool(parser_info.get("generic_parser_success") or False),
    }


def _source_payload(
    *,
    source: PropertySource,
    max_properties_per_source: int,
    timeout_ms: int,
    page_timeout_seconds: int,
    max_detail_pages: int,
    detail_timeout_seconds: int,
    disable_detail_extraction: bool,
    disable_platform_parsers: bool,
) -> dict[str, object]:
    return {
        "source_id": source.source_id,
        "office_name": source.office_name,
        "website": source.website,
        "root_domain": source.root_domain,
        "gemeente": source.gemeente,
        "province": source.province,
        "aanbod_url": source.aanbod_url,
        "detected_platform": source.detected_platform,
        "max_properties_per_source": max_properties_per_source,
        "timeout_ms": timeout_ms,
        "page_timeout_seconds": page_timeout_seconds,
        "max_detail_pages": max_detail_pages,
        "detail_timeout_seconds": detail_timeout_seconds,
        "disable_detail_extraction": disable_detail_extraction,
        "disable_platform_parsers": disable_platform_parsers,
    }


def _run_source_worker_subprocess(
    *,
    source: PropertySource,
    run_dir: Path,
    max_properties_per_source: int,
    timeout_ms: int,
    page_timeout_seconds: int,
    max_detail_pages: int,
    detail_timeout_seconds: int,
    disable_detail_extraction: bool,
    disable_platform_parsers: bool,
    source_timeout_seconds: int,
    output_path: Path,
) -> subprocess.CompletedProcess[str]:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False, dir=run_dir) as input_handle:
        input_path = Path(input_handle.name)
        json.dump(
            _source_payload(
                source=source,
                max_properties_per_source=max_properties_per_source,
                timeout_ms=timeout_ms,
                page_timeout_seconds=page_timeout_seconds,
                max_detail_pages=max_detail_pages,
                detail_timeout_seconds=detail_timeout_seconds,
                disable_detail_extraction=disable_detail_extraction,
                disable_platform_parsers=disable_platform_parsers,
            ),
            input_handle,
            ensure_ascii=True,
        )

    try:
        return subprocess.run(
            [sys.executable, str(_WORKER_SCRIPT_PATH), "--input", str(input_path), "--output", str(output_path)],
            capture_output=True,
            text=True,
            timeout=source_timeout_seconds,
            check=False,
        )
    finally:
        if input_path.exists():
            input_path.unlink()


def _crawl_source_in_subprocess(
    *,
    source: PropertySource,
    run_dir: Path,
    max_properties_per_source: int,
    timeout_ms: int,
    page_timeout_seconds: int,
    max_detail_pages: int,
    detail_timeout_seconds: int,
    disable_detail_extraction: bool,
    disable_platform_parsers: bool,
    source_timeout_seconds: int,
) -> tuple[CrawlResult, list[PropertyCandidate]]:
    started = time.perf_counter()
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False, dir=run_dir) as output_handle:
        output_path = Path(output_handle.name)

    try:
        try:
            completed = _run_source_worker_subprocess(
                source=source,
                run_dir=run_dir,
                max_properties_per_source=max_properties_per_source,
                timeout_ms=timeout_ms,
                page_timeout_seconds=page_timeout_seconds,
                max_detail_pages=max_detail_pages,
                detail_timeout_seconds=detail_timeout_seconds,
                disable_detail_extraction=disable_detail_extraction,
                disable_platform_parsers=disable_platform_parsers,
                source_timeout_seconds=source_timeout_seconds,
                output_path=output_path,
            )
        except subprocess.TimeoutExpired:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            if output_path.exists():
                try:
                    payload = json.loads(output_path.read_text(encoding="utf-8"))
                    accepted = [_deserialize_candidate(item) for item in payload.get("properties", [])]
                    rejected = [_deserialize_candidate(item) for item in payload.get("rejected", [])]
                    candidates = accepted + rejected
                    parser_info = _parser_info_from_payload(payload)
                    if candidates:
                        return (
                            CrawlResult(
                                source=source,
                                ok=False,
                                final_url=source.aanbod_url,
                                error=f"source timeout after {source_timeout_seconds}s; partial results preserved",
                                elapsed_ms=elapsed_ms,
                                timed_out=True,
                                parser_used=str(parser_info["parser_used"]),
                                realworks_parser_success=bool(parser_info["realworks_parser_success"]),
                                realworks_parser_failed=bool(parser_info["realworks_parser_failed"]),
                                parser_fallback_used=bool(parser_info["parser_fallback_used"]),
                                generic_parser_success=bool(parser_info["generic_parser_success"]),
                            ),
                            candidates,
                        )
                except (json.JSONDecodeError, TypeError, ValueError):
                    pass
            return (
                CrawlResult(
                    source=source,
                    ok=False,
                    final_url=source.aanbod_url,
                    error=f"source timeout after {source_timeout_seconds}s",
                    elapsed_ms=elapsed_ms,
                    timed_out=True,
                ),
                [],
            )

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        if not output_path.exists():
            detail_parts = [part.strip() for part in [completed.stderr or "", completed.stdout or ""] if part.strip()]
            return (
                CrawlResult(
                    source=source,
                    ok=False,
                    final_url=source.aanbod_url,
                    error=f"source worker missing output{': ' + '; '.join(detail_parts) if detail_parts else ''}",
                    elapsed_ms=elapsed_ms,
                ),
                [],
            )

        try:
            payload = json.loads(output_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            detail_parts = [f"invalid worker output: {exc}"]
            if completed.returncode != 0:
                detail_parts.append(f"worker exit code={completed.returncode}")
            if completed.stderr and completed.stderr.strip():
                detail_parts.append(f"stderr={completed.stderr.strip()}")
            if completed.stdout and completed.stdout.strip():
                detail_parts.append(f"stdout={completed.stdout.strip()}")
            return (
                CrawlResult(
                    source=source,
                    ok=False,
                    final_url=source.aanbod_url,
                    error="; ".join(detail_parts),
                    elapsed_ms=elapsed_ms,
                ),
                [],
            )
        accepted = [_deserialize_candidate(item) for item in payload.get("properties", [])]
        rejected = [_deserialize_candidate(item) for item in payload.get("rejected", [])]
        candidates = accepted + rejected
        errors = [str(item).strip() for item in payload.get("errors", []) if str(item).strip()]
        parser_info = _parser_info_from_payload(payload)
        if payload.get("status") == "succeeded":
            return (
                CrawlResult(
                    source=source,
                    ok=True,
                    final_url=source.aanbod_url,
                    error="",
                    elapsed_ms=elapsed_ms,
                    parser_used=str(parser_info["parser_used"]),
                    realworks_parser_success=bool(parser_info["realworks_parser_success"]),
                    realworks_parser_failed=bool(parser_info["realworks_parser_failed"]),
                    parser_fallback_used=bool(parser_info["parser_fallback_used"]),
                    generic_parser_success=bool(parser_info["generic_parser_success"]),
                ),
                candidates,
            )

        detail_parts = errors[:]
        if completed.returncode != 0:
            detail_parts.append(f"worker exit code={completed.returncode}")
        if completed.stderr and completed.stderr.strip():
            detail_parts.append(f"stderr={completed.stderr.strip()}")
        if completed.stdout and completed.stdout.strip():
            detail_parts.append(f"stdout={completed.stdout.strip()}")
        return (
            CrawlResult(
                source=source,
                ok=False,
                final_url=source.aanbod_url,
                error="; ".join(dict.fromkeys(detail_parts)) or "source worker failed",
                elapsed_ms=elapsed_ms,
                parser_used=str(parser_info["parser_used"]),
                realworks_parser_success=bool(parser_info["realworks_parser_success"]),
                realworks_parser_failed=bool(parser_info["realworks_parser_failed"]),
                parser_fallback_used=bool(parser_info["parser_fallback_used"]),
                generic_parser_success=bool(parser_info["generic_parser_success"]),
            ),
            candidates,
        )
    finally:
        if output_path.exists():
            output_path.unlink()


def run_property_discovery(
    *,
    province: str,
    max_sources: int,
    max_properties_per_source: int,
    source_csv_path: Path = DEFAULT_SOURCE_CSV_PATH,
    runs_base_dir: Path = DEFAULT_RUNS_BASE_DIR,
    latest_dir: Path = DEFAULT_LATEST_DIR,
    timeout_ms: int = 30000,
    source_timeout_seconds: int = 90,
    page_timeout_seconds: int = 30,
    max_detail_pages: int = 3,
    detail_timeout_seconds: int = 10,
    disable_detail_extraction: bool = False,
    platform: str = "",
    platform_fingerprint_input: Path = DEFAULT_PLATFORM_FINGERPRINT_INPUT,
    source_domain: str = "",
    disable_platform_parsers: bool = False,
    include_invalid_sources: bool = False,
    verbose: bool = True,
) -> PropertyDiscoveryRunOutput:
    started_at = _utc_now()
    run_id = _format_timestamp(started_at)
    run_id, run_dir = _create_run_dir(runs_base_dir, run_id)
    report_path = run_dir / REPORT_FILENAME

    loader = SourceLoader(source_csv_path)
    dedupe = PropertyDedupe()
    classifier = PropertyStatusClassifier()
    effective_timeout_ms = min(timeout_ms, page_timeout_seconds * 1000)

    if verbose:
        _log(
            "run started "
            f"province={province} max_sources={max_sources} max_properties_per_source={max_properties_per_source} "
            f"timeout_ms={timeout_ms} source_timeout_seconds={source_timeout_seconds} "
            f"page_timeout_seconds={page_timeout_seconds} max_detail_pages={max_detail_pages} "
            f"detail_timeout_seconds={detail_timeout_seconds} disable_detail_extraction={disable_detail_extraction} "
            f"platform={platform or 'all'} source_domain={source_domain or 'all'} "
            f"disable_platform_parsers={disable_platform_parsers} output_dir={run_dir}"
        )

    restore_latest_discovery_if_missing(source_csv_path)

    try:
        sources = [] if max_sources <= 0 else loader.load(
            province=province,
            max_sources=max_sources,
            include_invalid_sources=include_invalid_sources,
            platform_filter=platform,
            platform_fingerprint_path=platform_fingerprint_input,
            source_domain=source_domain,
        )
    except MissingSourceFileError as exc:
        finished_at = _utc_now()
        missing_path = Path(exc.csv_path)
        _write_missing_sources_report(
            report_path=report_path,
            run_id=run_id,
            province=province,
            started_at=started_at,
            finished_at=finished_at,
            missing_path=missing_path,
        )
        _log(f"ERROR missing source file: {_relative_windows_path(missing_path)}")
        _log("Run source discovery first or build the source master:")
        _log(_recommended_build_command(missing_path))
        return PropertyDiscoveryRunOutput(
            run_id=run_id,
            run_dir=run_dir,
            latest_dir=latest_dir,
            report_path=report_path,
            run_status="failed_missing_sources",
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            duration_seconds=max((finished_at - started_at).total_seconds(), 0.0),
            sources_loaded=0,
            sources_attempted=0,
            sources_succeeded=0,
            sources_failed=0,
            sources_timeout=0,
            sources_skipped_invalid_aanbod_url=0,
            total_property_candidates=0,
            deduped_properties=0,
            rejected_candidates=0,
        )
    if verbose:
        _log(f"sources loaded count={len(sources)}")
        _log(f"sources skipped invalid aanbod_url={loader.last_skipped_invalid_aanbod_url_count}")

    crawl_results: list[CrawlResult] = []
    candidates: list[PropertyCandidate] = []
    accepted_candidates: list[PropertyCandidate] = []
    rejected_candidates: list[PropertyCandidate] = []
    inventory: list[PropertyInventoryRecord] = []
    rejected_records: list[PropertyRejectedRecord] = []
    run_status = "completed"

    _write_checkpoint(
        run_dir=run_dir,
        report_path=report_path,
        run_id=run_id,
        province=province,
        run_status=run_status,
        started_at=started_at,
        finished_at=started_at,
        sources=sources,
        crawl_results=crawl_results,
        candidates=candidates,
        inventory=inventory,
        rejected=rejected_records,
        sources_skipped_invalid_aanbod_url=loader.last_skipped_invalid_aanbod_url_count,
    )

    try:
        for index, source in enumerate(sources, start=1):
            source_started = time.perf_counter()
            if verbose:
                _log(
                    f"source {index}/{len(sources)} START office_name={source.office_name} "
                    f"root_domain={source.root_domain} aanbod_url={source.aanbod_url}"
                )

            result, source_candidates = _crawl_source_in_subprocess(
                source=source,
                run_dir=run_dir,
                max_properties_per_source=max_properties_per_source,
                timeout_ms=effective_timeout_ms,
                page_timeout_seconds=page_timeout_seconds,
                max_detail_pages=max_detail_pages,
                detail_timeout_seconds=detail_timeout_seconds,
                disable_detail_extraction=disable_detail_extraction,
                disable_platform_parsers=disable_platform_parsers,
                source_timeout_seconds=source_timeout_seconds,
            )
            crawl_results.append(result)

            if result.ok:
                candidates.extend(source_candidates)
                source_accepted = sum(
                    1 for candidate in source_candidates if candidate.property_url_classification == "property_detail_candidate"
                )
                source_rejected = len(source_candidates) - source_accepted
                if verbose:
                    _log(
                        f"source {index}/{len(sources)} CANDIDATES found={len(source_candidates)} "
                        f"accepted={source_accepted} rejected={source_rejected}"
                    )
            elif result.timed_out:
                if source_candidates:
                    candidates.extend(source_candidates)
                if verbose:
                    _log(f"source {index}/{len(sources)} TIMEOUT error={result.error}")
            else:
                if verbose:
                    _log(f"source {index}/{len(sources)} ERROR error={result.error}")

            accepted_candidates, rejected_candidates, inventory, rejected_records = _build_outputs(
                candidates,
                run_id=run_id,
                dedupe=dedupe,
                classifier=classifier,
            )

            finished_at = _utc_now()
            _write_checkpoint(
                run_dir=run_dir,
                report_path=report_path,
                run_id=run_id,
                province=province,
                run_status="completed_with_errors" if any(not item.ok for item in crawl_results) else "completed",
                started_at=started_at,
                finished_at=finished_at,
                sources=sources,
                crawl_results=crawl_results,
                candidates=candidates,
                inventory=inventory,
                rejected=rejected_records,
                sources_skipped_invalid_aanbod_url=loader.last_skipped_invalid_aanbod_url_count,
            )

            if verbose:
                duration = time.perf_counter() - source_started
                _log(
                    f"source {index}/{len(sources)} DONE found={len(source_candidates)} "
                    f"accepted={sum(1 for candidate in source_candidates if candidate.property_url_classification == 'property_detail_candidate')} "
                    f"rejected={sum(1 for candidate in source_candidates if candidate.property_url_classification != 'property_detail_candidate')} "
                    f"duration={duration:.1f}s"
                )
    except KeyboardInterrupt:
        run_status = "interrupted"
        _log("keyboard interrupt received; saving partial results")
    finally:
        accepted_candidates, rejected_candidates, inventory, rejected_records = _build_outputs(
            candidates,
            run_id=run_id,
            dedupe=dedupe,
            classifier=classifier,
        )
        if run_status != "interrupted" and any(not result.ok for result in crawl_results):
            run_status = "completed_with_errors"
        finished_at = _utc_now()
        _write_checkpoint(
            run_dir=run_dir,
            report_path=report_path,
            run_id=run_id,
            province=province,
            run_status=run_status,
            started_at=started_at,
            finished_at=finished_at,
            sources=sources,
            crawl_results=crawl_results,
            candidates=candidates,
            inventory=inventory,
            rejected=rejected_records,
            sources_skipped_invalid_aanbod_url=loader.last_skipped_invalid_aanbod_url_count,
        )
        if run_status != "interrupted":
            copy_latest(
                run_dir,
                latest_dir,
                [
                    "property_candidates.csv",
                    INVENTORY_FILENAME,
                    LEGACY_INVENTORY_FILENAME,
                    REJECTED_FILENAME,
                    LEGACY_REJECTED_FILENAME,
                    REPORT_FILENAME,
                ],
            )
        if verbose:
            _log(
                f"run finished status={run_status} sources_processed={len(crawl_results)} "
                f"properties_found={len(candidates)} matching_ready={len(inventory)} rejected={len(rejected_records)} "
                f"report_path={report_path}"
            )

    return PropertyDiscoveryRunOutput(
        run_id=run_id,
        run_dir=run_dir,
        latest_dir=latest_dir,
        report_path=report_path,
        run_status=run_status,
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat(),
        duration_seconds=max((finished_at - started_at).total_seconds(), 0.0),
        sources_loaded=len(sources),
        sources_attempted=len(crawl_results),
        sources_succeeded=sum(1 for result in crawl_results if result.ok),
        sources_failed=sum(1 for result in crawl_results if not result.ok),
        sources_timeout=sum(1 for result in crawl_results if result.timed_out),
        sources_skipped_invalid_aanbod_url=loader.last_skipped_invalid_aanbod_url_count,
        total_property_candidates=len(candidates),
        deduped_properties=len(inventory),
        rejected_candidates=len(rejected_records),
    )
