from __future__ import annotations

import csv
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from domek_wonen.matching.matching_v1 import (
    _is_clean_available,
    _normalize_property_type,
    _normalize_text,
    _safe_int,
)


DEFAULT_BENCHMARK_CSV = Path("fixtures/benchmarks/kin_tilburg_250k_expected.csv")
DEFAULT_OUTPUT_BASE_DIR = Path("data/diagnostics/source_recovery")
DEFAULT_PROPERTY_DISCOVERY_RUNS_DIR = Path("data/property_discovery/runs")
CANDIDATES_FILENAME = "property_candidates.csv"
REJECTED_FILENAME = "property_rejected.csv"
MATCHING_READY_FILENAME = "matching_ready_inventory.csv"
REPORT_FILENAME = "source_recovery_report.md"
INVENTORY_FILENAME = "source_recovery_inventory.csv"
_HOUSE_NUMBER_RE = re.compile(r"\b\d+[a-z0-9/\-]*\b")


@dataclass(frozen=True)
class SourceRecoveryRunResult:
    run_id: str
    run_dir: Path
    benchmark_csv_path: Path
    property_discovery_run_dir: Path | None
    candidates_csv_path: Path | None
    rejected_csv_path: Path | None
    matching_ready_csv_path: Path | None
    report_path: Path
    inventory_output_path: Path
    benchmark_total: int
    available_only_expected_total: int
    found_in_candidates_count: int
    found_in_rejected_count: int
    found_in_matching_ready_count: int
    clean_available_count: int
    included_available_only_count: int
    gross_recovery_pct: float
    available_only_recovery_pct: float
    loss_by_stage: dict[str, int]
    loss_by_reason: dict[str, int]


def normalize_city(value: str) -> str:
    return _normalize_text(value or "")


def normalize_status(value: str) -> str:
    normalized = _normalize_text(value or "")
    mapping = {
        "beschikbaar": "beschikbaar",
        "available": "beschikbaar",
        "nieuw": "beschikbaar",
        "onder bod": "onder_bod",
        "onder_bod": "onder_bod",
        "verkocht": "verkocht",
        "sold": "verkocht",
        "verkocht ov": "verkocht_onder_voorbehoud",
        "verkocht onder voorbehoud": "verkocht_onder_voorbehoud",
        "sold subject to contract": "verkocht_onder_voorbehoud",
    }
    return mapping.get(normalized, normalized)


def normalize_address(value: str, city: str = "") -> str:
    normalized = _normalize_text(value or "")
    city_normalized = normalize_city(city)
    if city_normalized and normalized.endswith(f" {city_normalized}"):
        normalized = normalized[: -len(city_normalized)].strip()
    if city_normalized and normalized == city_normalized:
        return ""
    return normalized


def run_source_recovery_tracker(
    *,
    benchmark_csv_path: Path = DEFAULT_BENCHMARK_CSV,
    candidates_csv_path: Path | None = None,
    rejected_csv_path: Path | None = None,
    matching_ready_csv_path: Path | None = None,
    property_discovery_runs_dir: Path = DEFAULT_PROPERTY_DISCOVERY_RUNS_DIR,
    output_base_dir: Path = DEFAULT_OUTPUT_BASE_DIR,
) -> SourceRecoveryRunResult:
    discovery_run_dir, resolved_candidates_path, resolved_rejected_path, resolved_matching_ready_path = _resolve_artifact_paths(
        candidates_csv_path=candidates_csv_path,
        rejected_csv_path=rejected_csv_path,
        matching_ready_csv_path=matching_ready_csv_path,
        property_discovery_runs_dir=property_discovery_runs_dir,
    )

    expected_rows = _read_csv(benchmark_csv_path)
    candidate_rows = [_annotate_row(row, artifact_type="candidate") for row in _read_csv_if_exists(resolved_candidates_path)]
    rejected_rows = [_annotate_row(row, artifact_type="rejected") for row in _read_csv_if_exists(resolved_rejected_path)]
    matching_ready_rows = [_annotate_matching_ready_row(row) for row in _read_csv_if_exists(resolved_matching_ready_path)]

    result_rows = [
        _evaluate_expected_row(
            expected_row,
            candidate_rows=candidate_rows,
            rejected_rows=rejected_rows,
            matching_ready_rows=matching_ready_rows,
        )
        for expected_row in expected_rows
    ]

    run_id = _utc_run_id()
    run_dir = output_base_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    inventory_output_path = run_dir / INVENTORY_FILENAME
    _write_csv(inventory_output_path, result_rows, fieldnames=_output_fieldnames(expected_rows))

    benchmark_total = len(result_rows)
    available_only_expected_total = sum(1 for row in result_rows if row["status_expected_normalized"] == "beschikbaar")
    found_in_candidates_count = sum(1 for row in result_rows if _parse_bool(row["found_in_candidates"]))
    found_in_rejected_count = sum(1 for row in result_rows if _parse_bool(row["found_in_rejected"]))
    found_in_matching_ready_count = sum(1 for row in result_rows if _parse_bool(row["found_in_matching_ready"]))
    clean_available_count = sum(1 for row in result_rows if _parse_bool(row["found_clean_available"]))
    included_available_only_count = sum(1 for row in result_rows if _parse_bool(row["included_available_only"]))
    gross_recovery_pct = _pct(found_in_matching_ready_count, benchmark_total)
    available_only_recovery_pct = _pct(included_available_only_count, available_only_expected_total)
    loss_by_stage = dict(sorted(Counter(row["final_recovery_stage"] for row in result_rows).items()))
    loss_by_reason = dict(sorted(Counter(row["final_loss_reason"] for row in result_rows if row["final_loss_reason"]).items()))

    report_path = run_dir / REPORT_FILENAME
    report_path.write_text(
        _build_report(
            benchmark_csv_path=benchmark_csv_path,
            candidates_csv_path=resolved_candidates_path,
            rejected_csv_path=resolved_rejected_path,
            matching_ready_csv_path=resolved_matching_ready_path,
            benchmark_total=benchmark_total,
            available_only_expected_total=available_only_expected_total,
            found_in_candidates_count=found_in_candidates_count,
            found_in_rejected_count=found_in_rejected_count,
            found_in_matching_ready_count=found_in_matching_ready_count,
            clean_available_count=clean_available_count,
            included_available_only_count=included_available_only_count,
            gross_recovery_pct=gross_recovery_pct,
            available_only_recovery_pct=available_only_recovery_pct,
            loss_by_stage=loss_by_stage,
            loss_by_reason=loss_by_reason,
            result_rows=result_rows,
        ),
        encoding="utf-8",
    )

    return SourceRecoveryRunResult(
        run_id=run_id,
        run_dir=run_dir,
        benchmark_csv_path=benchmark_csv_path,
        property_discovery_run_dir=discovery_run_dir,
        candidates_csv_path=resolved_candidates_path,
        rejected_csv_path=resolved_rejected_path,
        matching_ready_csv_path=resolved_matching_ready_path,
        report_path=report_path,
        inventory_output_path=inventory_output_path,
        benchmark_total=benchmark_total,
        available_only_expected_total=available_only_expected_total,
        found_in_candidates_count=found_in_candidates_count,
        found_in_rejected_count=found_in_rejected_count,
        found_in_matching_ready_count=found_in_matching_ready_count,
        clean_available_count=clean_available_count,
        included_available_only_count=included_available_only_count,
        gross_recovery_pct=gross_recovery_pct,
        available_only_recovery_pct=available_only_recovery_pct,
        loss_by_stage=loss_by_stage,
        loss_by_reason=loss_by_reason,
    )


def _resolve_artifact_paths(
    *,
    candidates_csv_path: Path | None,
    rejected_csv_path: Path | None,
    matching_ready_csv_path: Path | None,
    property_discovery_runs_dir: Path,
) -> tuple[Path | None, Path | None, Path | None, Path | None]:
    explicit_paths = [path for path in (candidates_csv_path, rejected_csv_path, matching_ready_csv_path) if path is not None]
    if explicit_paths:
        run_dir = explicit_paths[0].parent
        return (
            run_dir,
            candidates_csv_path or _existing_path(run_dir / CANDIDATES_FILENAME),
            rejected_csv_path or _existing_path(run_dir / REJECTED_FILENAME),
            matching_ready_csv_path or _existing_path(run_dir / MATCHING_READY_FILENAME),
        )

    run_dirs = sorted(path for path in property_discovery_runs_dir.iterdir() if path.is_dir())
    for run_dir in reversed(run_dirs):
        candidates_path = _existing_path(run_dir / CANDIDATES_FILENAME)
        rejected_path = _existing_path(run_dir / REJECTED_FILENAME)
        matching_ready_path = _existing_path(run_dir / MATCHING_READY_FILENAME)
        if candidates_path or rejected_path or matching_ready_path:
            return run_dir, candidates_path, rejected_path, matching_ready_path
    raise FileNotFoundError(f"No PropertyDiscovery run artifacts found in {property_discovery_runs_dir}")


def _evaluate_expected_row(
    expected_row: dict[str, str],
    *,
    candidate_rows: list[dict[str, str]],
    rejected_rows: list[dict[str, str]],
    matching_ready_rows: list[dict[str, str]],
) -> dict[str, str]:
    expected_address = normalize_address(expected_row.get("address", ""), expected_row.get("city", ""))
    expected_city = normalize_city(expected_row.get("city", ""))
    expected_price = _safe_int(expected_row.get("price_eur", ""))
    expected_property_type = _normalize_property_type(expected_row.get("property_type", ""))
    expected_status = normalize_status(expected_row.get("status_expected", ""))

    matched_candidate = _match_rows(
        candidate_rows,
        expected_address=expected_address,
        expected_city=expected_city,
        expected_price=expected_price,
        expected_property_type=expected_property_type,
    )
    matched_rejected = _match_rows(
        rejected_rows,
        expected_address=expected_address,
        expected_city=expected_city,
        expected_price=expected_price,
        expected_property_type=expected_property_type,
    )
    matched_matching_ready = _match_rows(
        matching_ready_rows,
        expected_address=expected_address,
        expected_city=expected_city,
        expected_price=expected_price,
        expected_property_type=expected_property_type,
    )
    possible_match = _match_rows(
        candidate_rows + rejected_rows + matching_ready_rows,
        expected_address=expected_address,
        expected_city=expected_city,
        expected_price=expected_price,
        expected_property_type=expected_property_type,
        strong_only=False,
    )

    final_recovery_stage, final_loss_reason = _classify_final_stage(
        matched_candidate=matched_candidate,
        matched_rejected=matched_rejected,
        matched_matching_ready=matched_matching_ready,
        possible_match=possible_match,
    )

    candidate_url = ""
    if matched_candidate:
        candidate_url = matched_candidate.get("property_url", "")
    elif matched_rejected:
        candidate_url = matched_rejected.get("property_url", "")
    elif matched_matching_ready:
        candidate_url = matched_matching_ready.get("property_url", "")
    elif possible_match:
        candidate_url = possible_match.get("property_url", "")

    rejected_reason = ""
    if matched_rejected:
        rejected_reason = matched_rejected.get("rejection_reason", "") or matched_rejected.get("excluded_reason", "")

    matching_ready_reason = ""
    if matched_matching_ready:
        matching_ready_reason = (
            matched_matching_ready.get("review_reason", "")
            or matched_matching_ready.get("needs_review_reason", "")
            or matched_matching_ready.get("detail_error", "")
        )

    output_row = dict(expected_row)
    output_row["status_expected_normalized"] = expected_status
    output_row["found_in_candidates"] = "true" if matched_candidate else "false"
    output_row["found_in_rejected"] = "true" if matched_rejected else "false"
    output_row["found_in_matching_ready"] = "true" if matched_matching_ready else "false"
    output_row["found_clean_available"] = "true" if matched_matching_ready and _parse_bool(matched_matching_ready["found_clean_available"]) else "false"
    output_row["included_available_only"] = "true" if matched_matching_ready and _parse_bool(matched_matching_ready["included_available_only"]) else "false"
    output_row["candidate_url"] = candidate_url
    output_row["rejected_reason"] = rejected_reason
    output_row["matching_ready_reason"] = matching_ready_reason
    output_row["matched_property_id"] = matched_matching_ready.get("property_id", "") if matched_matching_ready else ""
    output_row["matched_property_url"] = matched_matching_ready.get("property_url", "") if matched_matching_ready else ""
    output_row["actual_city_raw"] = _first_non_empty(matched_matching_ready, matched_candidate, matched_rejected, field="city_raw")
    output_row["actual_price_eur"] = _first_non_empty(matched_matching_ready, matched_candidate, matched_rejected, field="price_eur")
    output_row["actual_property_type"] = _first_non_empty(matched_matching_ready, matched_candidate, matched_rejected, field="property_type")
    output_row["actual_rooms_count"] = _first_non_empty(matched_matching_ready, matched_candidate, matched_rejected, field="rooms_count")
    output_row["bedrooms_count"] = _first_non_empty(matched_matching_ready, matched_candidate, matched_rejected, field="bedrooms_count")
    output_row["actual_living_area_m2"] = _first_non_empty(matched_matching_ready, matched_candidate, matched_rejected, field="living_area_m2")
    output_row["status"] = _first_non_empty(matched_matching_ready, matched_candidate, matched_rejected, field="status") or _first_non_empty(
        matched_matching_ready, matched_candidate, matched_rejected, field="status_raw"
    )
    output_row["needs_review"] = _first_non_empty(matched_matching_ready, matched_candidate, matched_rejected, field="needs_review")
    output_row["address_quality"] = _first_non_empty(matched_matching_ready, matched_candidate, matched_rejected, field="address_quality")
    output_row["final_recovery_stage"] = final_recovery_stage
    output_row["final_loss_reason"] = final_loss_reason
    return output_row


def _classify_final_stage(
    *,
    matched_candidate: dict[str, str] | None,
    matched_rejected: dict[str, str] | None,
    matched_matching_ready: dict[str, str] | None,
    possible_match: dict[str, str] | None,
) -> tuple[str, str]:
    if matched_matching_ready:
        if _parse_bool(matched_matching_ready["found_clean_available"]) and _parse_bool(matched_matching_ready["included_available_only"]):
            return "found_clean_included", ""
        if not _parse_bool(matched_matching_ready["included_available_only"]):
            status = matched_matching_ready.get("status_normalized", "") or normalize_status(matched_matching_ready.get("status", ""))
            return "found_but_status_excluded", f"status_excluded:{status or 'unknown'}"
        return "matching_ready_but_not_clean", _matching_ready_not_clean_reason(matched_matching_ready)

    if matched_rejected:
        reason = matched_rejected.get("rejection_reason", "") or matched_rejected.get("excluded_reason", "") or "candidate_rejected"
        return "candidate_seen_but_rejected", reason

    if matched_candidate:
        reason = matched_candidate.get("needs_review_reason", "") or matched_candidate.get("review_reason", "") or "not_promoted_to_matching_ready"
        return "candidate_seen_not_matching_ready", reason

    if possible_match:
        reason = possible_match.get("address_raw", "") or possible_match.get("title", "") or "possible_address_match"
        return "possible_match_needs_review", f"possible_address_match:{reason}"

    return "not_seen_in_candidates", "missing_address_city_match_in_candidates"


def _matching_ready_not_clean_reason(row: dict[str, str]) -> str:
    reasons = [
        "needs_review" if _parse_bool(row.get("needs_review", "")) else "",
        f"address_quality:{row.get('address_quality', '').strip().lower()}" if row.get("address_quality", "").strip().lower() not in {"", "valid"} else "",
        "missing_price" if _safe_int(row.get("price_eur", "")) is None else "",
    ]
    joined = ",".join(reason for reason in reasons if reason)
    return joined or "matching_ready_not_clean"


def _match_rows(
    rows: list[dict[str, str]],
    *,
    expected_address: str,
    expected_city: str,
    expected_price: int | None,
    expected_property_type: str,
    strong_only: bool = True,
) -> dict[str, str] | None:
    if strong_only:
        strong_matches = [
            row
            for row in rows
            if row["address_normalized"] == expected_address and row["city_normalized"] == expected_city
        ]
        return _pick_best_match(strong_matches, expected_price=expected_price, expected_property_type=expected_property_type) if strong_matches else None

    possible_matches = [
        row
        for row in rows
        if _is_possible_address_match(expected_address, row["address_normalized"])
        and (not expected_city or row["city_normalized"] == expected_city or not row["city_normalized"])
    ]
    return _pick_best_match(possible_matches, expected_price=expected_price, expected_property_type=expected_property_type) if possible_matches else None


def _annotate_row(row: dict[str, str], *, artifact_type: str) -> dict[str, str]:
    annotated = dict(row)
    annotated["artifact_type"] = artifact_type
    annotated["address_normalized"] = normalize_address(row.get("address_raw", ""), row.get("city_raw", ""))
    annotated["city_normalized"] = normalize_city(row.get("city_raw", "") or row.get("gemeente", ""))
    annotated["status_normalized"] = normalize_status(row.get("status", "") or row.get("status_raw", ""))
    annotated["price_eur"] = row.get("price_eur", "") or str(_safe_int(row.get("price_raw", "")) or "")
    return annotated


def _annotate_matching_ready_row(row: dict[str, str]) -> dict[str, str]:
    annotated = _annotate_row(row, artifact_type="matching_ready")
    annotated["found_clean_available"] = "true" if _is_clean_available(row) else "false"
    annotated["included_available_only"] = "true" if normalize_status(row.get("status", "")) == "beschikbaar" else "false"
    return annotated


def _pick_best_match(
    rows: list[dict[str, str]],
    *,
    expected_price: int | None,
    expected_property_type: str,
) -> dict[str, str]:
    return sorted(
        rows,
        key=lambda row: (
            0 if _normalize_property_type(row.get("property_type", "")) == expected_property_type and expected_property_type else 1,
            abs((_safe_int(row.get("price_eur", "")) or 0) - expected_price) if expected_price is not None else 0,
            row.get("property_id", ""),
            row.get("property_url", ""),
        ),
    )[0]


def _is_possible_address_match(expected_address: str, actual_address: str) -> bool:
    if not expected_address or not actual_address:
        return False
    if expected_address == actual_address:
        return True
    expected_number = _extract_house_number(expected_address)
    actual_number = _extract_house_number(actual_address)
    if not expected_number or not actual_number or expected_number != actual_number:
        return False
    expected_street = _strip_house_number(expected_address)
    actual_street = _strip_house_number(actual_address)
    return bool(expected_street and actual_street and (expected_street in actual_street or actual_street in expected_street))


def _extract_house_number(value: str) -> str:
    match = _HOUSE_NUMBER_RE.search(value or "")
    return match.group(0) if match else ""


def _strip_house_number(value: str) -> str:
    return " ".join(_HOUSE_NUMBER_RE.sub(" ", value or "").split())


def _build_report(
    *,
    benchmark_csv_path: Path,
    candidates_csv_path: Path | None,
    rejected_csv_path: Path | None,
    matching_ready_csv_path: Path | None,
    benchmark_total: int,
    available_only_expected_total: int,
    found_in_candidates_count: int,
    found_in_rejected_count: int,
    found_in_matching_ready_count: int,
    clean_available_count: int,
    included_available_only_count: int,
    gross_recovery_pct: float,
    available_only_recovery_pct: float,
    loss_by_stage: dict[str, int],
    loss_by_reason: dict[str, int],
    result_rows: list[dict[str, str]],
) -> str:
    stage_lines = [f"- {stage}: {count}" for stage, count in loss_by_stage.items()] or ["- None"]
    reason_lines = [f"- {reason}: {count}" for reason, count in loss_by_reason.items()] or ["- None"]
    focus_addresses = [
        "Trouwlaan 285",
        "Roemerhof 16",
        "Roemerhof 29",
        "Roemerhof 5",
        "Roemerhof 26",
        "Korte Nieuwstraat 112",
    ]
    focus_lookup = {normalize_address(row.get("address", ""), row.get("city", "")): row for row in result_rows}
    focus_rows = [focus_lookup.get(normalize_address(address, "Tilburg")) for address in focus_addresses]
    focus_table = [
        "| address | stage | found_in_candidates | found_in_rejected | found_in_matching_ready | found_clean_available | included_available_only | final_loss_reason |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in focus_rows:
        if not row:
            continue
        focus_table.append(
            f"| {row['address']} | {row['final_recovery_stage']} | {row['found_in_candidates']} | {row['found_in_rejected']} | {row['found_in_matching_ready']} | {row['found_clean_available']} | {row['included_available_only']} | {row['final_loss_reason'] or '-'} |"
        )
    return "\n".join(
        [
            "# KIN Source Recovery Report",
            "",
            f"- Benchmark CSV: {benchmark_csv_path}",
            f"- Candidates CSV: {candidates_csv_path or 'not found'}",
            f"- Rejected CSV: {rejected_csv_path or 'not found'}",
            f"- Matching Ready CSV: {matching_ready_csv_path or 'not found'}",
            f"- benchmark_total: {benchmark_total}",
            f"- available_only_expected_total: {available_only_expected_total}",
            f"- found_in_candidates_count: {found_in_candidates_count}",
            f"- found_in_rejected_count: {found_in_rejected_count}",
            f"- found_in_matching_ready_count: {found_in_matching_ready_count}",
            f"- clean_available_count: {clean_available_count}",
            f"- included_available_only_count: {included_available_only_count}",
            f"- gross_recovery_pct: {gross_recovery_pct:.1f}",
            f"- available_only_recovery_pct: {available_only_recovery_pct:.1f}",
            "",
            "## loss_by_stage",
            *stage_lines,
            "",
            "## loss_by_reason",
            *reason_lines,
            "",
            "## KIN focus table",
            *focus_table,
            "",
        ]
    )


def _output_fieldnames(expected_rows: list[dict[str, str]]) -> list[str]:
    expected_fieldnames = list(expected_rows[0].keys()) if expected_rows else []
    return expected_fieldnames + [
        "status_expected_normalized",
        "found_in_candidates",
        "found_in_rejected",
        "found_in_matching_ready",
        "found_clean_available",
        "included_available_only",
        "candidate_url",
        "rejected_reason",
        "matching_ready_reason",
        "matched_property_id",
        "matched_property_url",
        "actual_city_raw",
        "actual_price_eur",
        "actual_property_type",
        "actual_rooms_count",
        "bedrooms_count",
        "actual_living_area_m2",
        "status",
        "needs_review",
        "address_quality",
        "final_recovery_stage",
        "final_loss_reason",
    ]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_csv_if_exists(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    return _read_csv(path)


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _first_non_empty(*rows: dict[str, str] | None, field: str) -> str:
    for row in rows:
        if row and row.get(field, ""):
            return row.get(field, "")
    return ""


def _existing_path(path: Path) -> Path | None:
    return path if path.exists() else None


def _parse_bool(value: str) -> bool:
    return str(value).strip().casefold() in {"1", "true", "yes", "y"}


def _pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 1)


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
