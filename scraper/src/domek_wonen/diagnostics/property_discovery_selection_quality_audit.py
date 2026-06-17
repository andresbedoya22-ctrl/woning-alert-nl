from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from domek_wonen.discovery.discovery_artifacts import _find_latest_valid_run
from domek_wonen.matching.matching_v1 import _is_clean_available, _normalize_text, _safe_int
from domek_wonen.properties.platform_parser_registry import (
    detect_platform_for_row,
    get_platform_parser,
    load_platform_assignments,
)


BASE_DIR = Path(__file__).resolve().parents[4]
DEFAULT_OUTPUT_BASE_DIR = BASE_DIR / "data" / "diagnostics" / "property_discovery_selection_quality"
DEFAULT_SOURCE_MASTER_PATH = BASE_DIR / "data" / "discovery" / "latest" / "makelaar_sources_master.csv"
DEFAULT_OVERRIDE_CSV_PATH = BASE_DIR / "data" / "discovery" / "reference" / "property_discovery_source_overrides.csv"
DEFAULT_PLATFORM_FINGERPRINT_PATH = BASE_DIR / "data" / "discovery" / "platform_fingerprint" / "platform_fingerprint_results.csv"
DEFAULT_DISCOVERY_RUNS_DIR = BASE_DIR / "data" / "discovery" / "runs"
DEFAULT_PROPERTY_DISCOVERY_RUNS_DIR = BASE_DIR / "data" / "property_discovery" / "runs"
CURRENT_RUN_FILENAMES = (
    "property_candidates.csv",
    "matching_ready_inventory.csv",
    "rejected_property_candidates.csv",
)
OUTPUT_INVENTORY_FILENAME = "selection_quality_inventory.csv"
OUTPUT_REPORT_FILENAME = "selection_quality_report.md"

CSV_FIELDNAMES = [
    "source_id",
    "office_name",
    "source_domain",
    "city",
    "province",
    "detected_platform",
    "supported_parser",
    "eligible_for_property_discovery",
    "included_in_current_run",
    "included_by_override",
    "included_in_baseline_or_previous_validated_run",
    "excluded_by_max_sources_or_priority",
    "excluded_by_legal_status",
    "excluded_by_missing_aanbod_url",
    "unsupported_platform",
    "reason_if_not_in_current_run",
    "kin_current_run_status",
    "kin_current_run_reason",
    "candidates_found",
    "accepted_candidates",
    "rejected_candidates",
    "matching_ready",
    "clean_available",
    "unknown_status_count",
    "invalid_price_count",
    "invalid_address_count",
    "invalid_city_count",
    "needs_review_count",
    "sold_count",
    "sold_ov_count",
    "onder_bod_count",
    "top_rejection_reasons",
    "top_needs_review_reasons",
    "quality_score",
    "recommended_action",
    "total_matching_ready",
    "properties_in_target_city",
    "properties_outside_target_city",
    "target_city_clean_available",
    "outside_city_clean_available",
    "target_city_unknown_status",
    "target_city_invalid_price",
    "city_distribution_top_10",
    "can_support_city_specific_search",
    "filtering_risk",
]


@dataclass(frozen=True)
class PropertyDiscoverySelectionQualityAuditResult:
    run_id: str
    run_dir: Path
    report_path: Path
    inventory_path: Path
    source_master_path: Path
    property_discovery_run_dir: Path
    source_rows: list[dict[str, str]]
    recommended_decision: str


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _bool_str(value: bool) -> str:
    return "true" if value else "false"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_csv_if_exists(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    return _read_csv(path)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _normalize_province(value: str) -> str:
    return _normalize_text((value or "").replace("-", " "))


def _normalize_source_domain(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized.startswith("http://") or normalized.startswith("https://"):
        normalized = normalized.split("://", 1)[1]
    return normalized.strip().strip("/")


def _extract_domain(row: dict[str, str]) -> str:
    return _normalize_source_domain(row.get("root_domain", "") or row.get("website", "") or row.get("aanbod_url", ""))


def _row_key(row: dict[str, str]) -> tuple[str, str, str]:
    source_id = (row.get("source_id") or "").strip().lower()
    if source_id:
        return ("source_id", source_id, "")
    return (
        _extract_domain(row),
        _normalize_text(row.get("gemeente", "")),
        _normalize_province(row.get("province", "") or row.get("provincie", "")),
    )


def _resolve_source_master_path(path: Path | None) -> Path:
    if path is not None:
        if path.exists():
            return path
        raise FileNotFoundError(f"Source master not found: {path}")
    if DEFAULT_SOURCE_MASTER_PATH.exists():
        return DEFAULT_SOURCE_MASTER_PATH
    selected_run = _find_latest_valid_run(DEFAULT_DISCOVERY_RUNS_DIR)
    if selected_run is None:
        raise FileNotFoundError(
            f"Source master not found. Expected {DEFAULT_SOURCE_MASTER_PATH} or a valid run in {DEFAULT_DISCOVERY_RUNS_DIR}."
        )
    return selected_run / "makelaar_sources_master.csv"


def _resolve_property_discovery_run_dir(path: Path) -> Path:
    if path.exists() and path.is_dir():
        return path
    raise FileNotFoundError(f"PropertyDiscovery run dir not found: {path}")


def _load_override_rows(path: Path | None) -> tuple[list[dict[str, str]], set[tuple[str, str, str]]]:
    if path is None or not path.exists():
        return [], set()
    rows = _read_csv(path)
    return rows, {_row_key(row) for row in rows}


def _merge_source_rows(base_rows: list[dict[str, str]], override_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    if not override_rows:
        return base_rows
    row_by_key: dict[tuple[str, str, str], dict[str, str]] = {}
    base_order: list[tuple[str, str, str]] = []
    for row in base_rows:
        key = _row_key(row)
        if key not in row_by_key:
            base_order.append(key)
        row_by_key[key] = dict(row)

    override_order: list[tuple[str, str, str]] = []
    for row in override_rows:
        key = _row_key(row)
        override_order.append(key)
        merged = dict(row_by_key.get(key, {}))
        for field, value in row.items():
            if value is not None and value != "":
                merged[field] = value
        row_by_key[key] = merged

    override_keys = set(override_order)
    merged_rows = [row_by_key[key] for key in override_order]
    merged_rows.extend(row_by_key[key] for key in base_order if key not in override_keys)
    return merged_rows


def _load_current_run_artifacts(run_dir: Path) -> dict[str, list[dict[str, str]]]:
    return {filename: _read_csv_if_exists(run_dir / filename) for filename in CURRENT_RUN_FILENAMES}


def _source_domain_from_artifact_row(row: dict[str, str]) -> str:
    for field in ("source_root_domain", "root_domain", "source_domain"):
        value = _normalize_source_domain(row.get(field, ""))
        if value:
            return value
    for field in ("source_aanbod_url", "source_url"):
        value = _normalize_source_domain(row.get(field, ""))
        if value:
            return value
    return ""


def _index_rows_by_domain(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    indexed: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        domain = _source_domain_from_artifact_row(row)
        if domain:
            indexed[domain].append(row)
    return indexed


def _domain_seen_in_run(run_rows: dict[str, list[dict[str, str]]]) -> set[str]:
    seen: set[str] = set()
    for rows in run_rows.values():
        seen.update(_index_rows_by_domain(rows).keys())
    return seen


def _load_previous_validated_runs(
    runs_dir: Path,
    current_run_dir: Path,
) -> dict[str, set[str]]:
    previous_runs_by_domain: dict[str, set[str]] = defaultdict(set)
    if not runs_dir.exists():
        return previous_runs_by_domain
    for candidate in sorted((item for item in runs_dir.iterdir() if item.is_dir()), key=lambda item: item.name):
        if candidate.resolve() == current_run_dir.resolve():
            continue
        present = False
        for filename in CURRENT_RUN_FILENAMES:
            path = candidate / filename
            if not path.exists():
                continue
            present = True
            for row in _read_csv(path):
                domain = _source_domain_from_artifact_row(row)
                if domain:
                    previous_runs_by_domain[domain].add(candidate.name)
        if not present:
            continue
    return previous_runs_by_domain


def _normalize_city_label(value: str) -> str:
    cleaned = re.sub(r"\b\d{4}\s*[a-zA-Z]{2}\b", " ", value or "", flags=re.IGNORECASE)
    cleaned = re.sub(r"[^A-Za-zÀ-ÿ' -]+", " ", cleaned)
    return " ".join(cleaned.split()).strip()


def _city_matches_target(city_raw: str, target_city: str) -> bool:
    normalized_target = _normalize_text(target_city)
    normalized_city = _normalize_text(_normalize_city_label(city_raw))
    if not normalized_city or not normalized_target:
        return False
    if normalized_city == normalized_target:
        return True
    return normalized_city.endswith(f" {normalized_target}") or f" {normalized_target} " in f" {normalized_city} "


def _city_distribution(rows: list[dict[str, str]]) -> str:
    counter: Counter[str] = Counter()
    for row in rows:
        city_label = _normalize_city_label(row.get("city_raw", "")) or "missing"
        counter[city_label] += 1
    if not counter:
        return "none"
    return ", ".join(f"{label} ({count})" for label, count in counter.most_common(10))


def _counter_summary(counter: Counter[str], limit: int = 5) -> str:
    filtered = [(name, count) for name, count in counter.most_common(limit) if name]
    if not filtered:
        return "none"
    return ", ".join(f"{name} ({count})" for name, count in filtered)


def _count_invalid_price(rows: list[dict[str, str]]) -> int:
    return sum(1 for row in rows if (row.get("needs_review_reason") or "") == "invalid_price")


def _count_invalid_city(rows: list[dict[str, str]]) -> int:
    return sum(1 for row in rows if (row.get("needs_review_reason") or "") == "invalid_city_raw")


def _count_unknown_status(rows: list[dict[str, str]]) -> int:
    return sum(1 for row in rows if (row.get("status") or "").strip() == "unknown")


def _count_needs_review(rows: list[dict[str, str]]) -> int:
    return sum(1 for row in rows if (row.get("needs_review") or "").strip().lower() == "true")


def _count_status(rows: list[dict[str, str]], *statuses: str) -> int:
    allowed = {status.strip().lower() for status in statuses}
    return sum(1 for row in rows if (row.get("status") or "").strip().lower() in allowed)


def _rejection_counter(rows: list[dict[str, str]]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for row in rows:
        reason = (row.get("rejection_reason") or "").strip()
        if reason:
            counter[reason] += 1
    return counter


def _needs_review_counter(*row_groups: list[dict[str, str]]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for rows in row_groups:
        for row in rows:
            reason = (row.get("needs_review_reason") or "").strip()
            if reason:
                counter[reason] += 1
    return counter


def _quality_score(
    *,
    candidates_found: int,
    clean_available: int,
    rejected_candidates: int,
    needs_review_count: int,
    invalid_price_count: int,
    invalid_address_count: int,
    invalid_city_count: int,
    unknown_status_count: int,
) -> int:
    score = 40
    score += min(clean_available * 8, 40)
    score += min(candidates_found, 10)
    score -= rejected_candidates * 2
    score -= needs_review_count * 2
    score -= invalid_price_count * 3
    score -= invalid_address_count * 3
    score -= invalid_city_count * 4
    score -= unknown_status_count * 3
    return max(0, min(100, score))


def _recommended_action(
    *,
    source_domain: str,
    candidates_found: int,
    rejected_candidates: int,
    matching_ready: int,
    clean_available: int,
    needs_review_count: int,
    unknown_status_count: int,
    invalid_price_count: int,
    invalid_address_count: int,
    invalid_city_count: int,
    sold_count: int,
    sold_ov_count: int,
    onder_bod_count: int,
) -> str:
    total_status_rows = sold_count + sold_ov_count + onder_bod_count
    commercially_relevant = source_domain in {
        "allroundmakelaardij.nl",
        "alstedevanmierlomakelaardij.nl",
        "cvda.nl",
        "hansvanberkel.nl",
        "jurgensmakelaardij.nl",
        "kinmakelaars.nl",
    }
    if candidates_found < 3 and matching_ready < 3:
        return "not_enough_data"
    if matching_ready > 0 and total_status_rows == matching_ready and clean_available == 0:
        return "temporarily_pause_scaling"
    if clean_available >= 5 and needs_review_count <= max(1, matching_ready // 4):
        return "keep_and_scale"
    if invalid_city_count >= max(2, matching_ready // 3):
        return "fix_city_extraction"
    if invalid_address_count >= max(2, matching_ready // 3):
        return "fix_address_extraction"
    if invalid_price_count >= max(2, matching_ready // 3):
        return "fix_price_extraction"
    if unknown_status_count >= max(2, matching_ready // 3):
        return "fix_status_extraction"
    if matching_ready <= 2 and rejected_candidates >= max(3, matching_ready + 2):
        return "inspect_source_manually"
    if commercially_relevant and clean_available == 0 and (matching_ready > 0 or candidates_found >= 4):
        return "needs_parser_or_quality_fix"
    if rejected_candidates >= candidates_found and candidates_found > 0:
        return "inspect_source_manually"
    return "temporarily_pause_scaling" if clean_available == 0 and total_status_rows > 0 else "not_enough_data"


def _filtering_risk(
    *,
    total_matching_ready: int,
    properties_in_target_city: int,
    outside_city_clean_available: int,
    invalid_city_count: int,
    target_city_unknown_status: int,
) -> str:
    if total_matching_ready == 0:
        return "high"
    if invalid_city_count >= max(2, total_matching_ready // 3):
        return "high"
    if properties_in_target_city == 0 and outside_city_clean_available > 0:
        return "high"
    if target_city_unknown_status > 0 or outside_city_clean_available > properties_in_target_city:
        return "medium"
    return "low"


def _selection_reason(
    *,
    included_in_current_run: bool,
    eligible_for_property_discovery: bool,
    excluded_by_legal_status: bool,
    excluded_by_missing_aanbod_url: bool,
    unsupported_platform: bool,
    included_by_override: bool,
    previous_runs: set[str],
    is_active: bool,
) -> tuple[bool, str]:
    if included_in_current_run:
        return False, "included_in_current_run"
    if not is_active:
        return False, "inactive_source"
    if excluded_by_legal_status:
        return False, "excluded_by_legal_status"
    if excluded_by_missing_aanbod_url:
        return False, "excluded_by_missing_aanbod_url"
    if unsupported_platform:
        return False, "unsupported_platform"
    if included_by_override:
        return False, "listed_in_override_but_not_seen_in_run"
    if eligible_for_property_discovery and previous_runs:
        return True, "eligible_supported_source_not_selected_in_current_batch"
    if eligible_for_property_discovery:
        return True, "eligible_source_not_selected_in_current_batch"
    return False, "not_eligible_for_property_discovery"


def _build_report(
    *,
    run_id: str,
    city: str,
    province: str,
    source_master_path: Path,
    property_discovery_run_dir: Path,
    rows: list[dict[str, str]],
    recommended_decision: str,
) -> str:
    selection_counts = Counter()
    quality_counts = Counter()
    filtering_counts = Counter()
    for row in rows:
        if row["included_in_current_run"] == "true":
            selection_counts["included_in_current_run"] += 1
        if row["included_by_override"] == "true":
            selection_counts["included_by_override"] += 1
        if row["included_in_baseline_or_previous_validated_run"] == "true":
            selection_counts["included_in_baseline_or_previous_validated_run"] += 1
        if row["excluded_by_max_sources_or_priority"] == "true":
            selection_counts["excluded_by_max_sources_or_priority"] += 1
        if row["excluded_by_legal_status"] == "true":
            selection_counts["excluded_by_legal_status"] += 1
        if row["excluded_by_missing_aanbod_url"] == "true":
            selection_counts["excluded_by_missing_aanbod_url"] += 1
        if row["unsupported_platform"] == "true":
            selection_counts["unsupported_platform"] += 1
        quality_counts[row["recommended_action"]] += 1
        filtering_counts[row["filtering_risk"]] += 1

    kin_row = next((row for row in rows if row["source_domain"] == "kinmakelaars.nl"), None)
    lines = [
        "# PropertyDiscovery Source Selection + Batch Quality Audit v1",
        "",
        f"- run_timestamp: {run_id}",
        f"- city: {city}",
        f"- province: {province}",
        f"- source_master_path: {source_master_path}",
        f"- property_discovery_run_dir: {property_discovery_run_dir}",
        f"- sources_audited: {len(rows)}",
        f"- recommended_decision: {recommended_decision}",
        "",
        "## Part A - Source Selection",
        f"- eligible_for_property_discovery: {sum(1 for row in rows if row['eligible_for_property_discovery'] == 'true')}",
        f"- included_in_current_run: {selection_counts.get('included_in_current_run', 0)}",
        f"- included_by_override: {selection_counts.get('included_by_override', 0)}",
        f"- included_in_baseline_or_previous_validated_run: {selection_counts.get('included_in_baseline_or_previous_validated_run', 0)}",
        f"- excluded_by_max_sources_or_priority: {selection_counts.get('excluded_by_max_sources_or_priority', 0)}",
        f"- excluded_by_legal_status: {selection_counts.get('excluded_by_legal_status', 0)}",
        f"- excluded_by_missing_aanbod_url: {selection_counts.get('excluded_by_missing_aanbod_url', 0)}",
        f"- unsupported_platform: {selection_counts.get('unsupported_platform', 0)}",
    ]
    if kin_row is not None:
        lines.extend(
            [
                f"- KIN current_run_status: {kin_row['kin_current_run_status']}",
                f"- KIN current_run_reason: {kin_row['kin_current_run_reason']}",
            ]
        )

    lines.extend(["", "## Part B - Quality Per Source"])
    for row in rows:
        lines.append(
            f"- {row['source_domain']}: candidates_found={row['candidates_found']}, matching_ready={row['matching_ready']}, "
            f"clean_available={row['clean_available']}, quality_score={row['quality_score']}, "
            f"recommended_action={row['recommended_action']}, top_rejection_reasons={row['top_rejection_reasons']}, "
            f"top_needs_review_reasons={row['top_needs_review_reasons']}"
        )

    lines.extend(
        [
            "",
            "## Part C - Target Area Filtering",
            f"- filtering_risk_low: {filtering_counts.get('low', 0)}",
            f"- filtering_risk_medium: {filtering_counts.get('medium', 0)}",
            f"- filtering_risk_high: {filtering_counts.get('high', 0)}",
        ]
    )
    for row in rows:
        lines.append(
            f"- {row['source_domain']}: target_city={row['properties_in_target_city']}, outside_city={row['properties_outside_target_city']}, "
            f"target_city_clean_available={row['target_city_clean_available']}, outside_city_clean_available={row['outside_city_clean_available']}, "
            f"can_support_city_specific_search={row['can_support_city_specific_search']}, filtering_risk={row['filtering_risk']}, "
            f"city_distribution_top_10={row['city_distribution_top_10']}"
        )

    lines.extend(["", "## Action Summary"])
    for action, count in quality_counts.most_common():
        lines.append(f"- {action}: {count}")
    return "\n".join(lines) + "\n"


def run_property_discovery_selection_quality_audit(
    *,
    city: str,
    province: str,
    property_discovery_run_dir: Path,
    source_domains: list[str] | None = None,
    source_master_path: Path | None = None,
    override_csv_path: Path | None = DEFAULT_OVERRIDE_CSV_PATH,
    platform_fingerprint_path: Path | None = DEFAULT_PLATFORM_FINGERPRINT_PATH,
    property_discovery_runs_dir: Path = DEFAULT_PROPERTY_DISCOVERY_RUNS_DIR,
    output_base_dir: Path = DEFAULT_OUTPUT_BASE_DIR,
) -> PropertyDiscoverySelectionQualityAuditResult:
    effective_override_csv_path = override_csv_path if override_csv_path is not None else DEFAULT_OVERRIDE_CSV_PATH
    effective_platform_fingerprint_path = (
        platform_fingerprint_path if platform_fingerprint_path is not None else DEFAULT_PLATFORM_FINGERPRINT_PATH
    )
    resolved_source_master_path = _resolve_source_master_path(source_master_path)
    resolved_run_dir = _resolve_property_discovery_run_dir(property_discovery_run_dir)
    current_run_rows = _load_current_run_artifacts(resolved_run_dir)
    current_domains = _domain_seen_in_run(current_run_rows)
    previous_runs_by_domain = _load_previous_validated_runs(property_discovery_runs_dir, resolved_run_dir)
    override_rows, override_keys = _load_override_rows(effective_override_csv_path)
    override_domains = {_extract_domain(row) for row in override_rows if _extract_domain(row)}
    platform_assignments = load_platform_assignments(effective_platform_fingerprint_path)
    current_candidates = _index_rows_by_domain(current_run_rows["property_candidates.csv"])
    current_inventory = _index_rows_by_domain(current_run_rows["matching_ready_inventory.csv"])
    current_rejected = _index_rows_by_domain(current_run_rows["rejected_property_candidates.csv"])

    normalized_city = _normalize_text(city)
    normalized_province = _normalize_province(province)
    domain_filter = {_normalize_source_domain(value) for value in (source_domains or []) if _normalize_source_domain(value)}

    source_rows = _merge_source_rows(_read_csv(resolved_source_master_path), override_rows)
    filtered_sources = []
    for row in source_rows:
        row_domain = _extract_domain(row)
        if domain_filter and row_domain not in domain_filter:
            continue
        if _normalize_text(row.get("gemeente", "")) != normalized_city:
            continue
        if _normalize_province(row.get("province", "") or row.get("provincie", "")) != normalized_province:
            continue
        filtered_sources.append(row)

    output_rows: list[dict[str, str]] = []
    for source_row in filtered_sources:
        source_id = (source_row.get("source_id") or "").strip()
        source_domain = _extract_domain(source_row)
        detected_platform = detect_platform_for_row(source_row, platform_assignments)
        supported_parser = get_platform_parser(detected_platform) is not None
        legal_status = (source_row.get("legal_status") or "").strip()
        aanbod_url = (source_row.get("aanbod_url") or "").strip()
        aanbod_url_quality = (source_row.get("aanbod_url_quality") or "").strip()
        aanbod_url_type = (source_row.get("aanbod_url_type") or "").strip()
        source_quality_status = (source_row.get("source_quality_status") or "").strip()
        is_active = (source_row.get("is_active") or "").strip().lower() == "true"
        excluded_by_legal_status = legal_status != "allowed_official_source"
        excluded_by_missing_aanbod_url = not aanbod_url or aanbod_url_quality != "valid"
        excluded_invalid_source = aanbod_url_type == "property_detail" or source_quality_status == "invalid"
        eligible_for_property_discovery = (
            is_active
            and not excluded_by_legal_status
            and not excluded_by_missing_aanbod_url
            and not excluded_invalid_source
        )
        unsupported_platform = bool(detected_platform) and not supported_parser
        included_in_current_run = source_domain in current_domains
        included_by_override = _row_key(source_row) in override_keys or source_domain in override_domains
        previous_runs = previous_runs_by_domain.get(source_domain, set())
        included_in_baseline_or_previous_validated_run = bool(previous_runs) or (
            "property_discovery_supported_batch" in (source_row.get("source_origin") or "").strip().lower()
        )
        excluded_by_max_sources_or_priority, reason_if_not_in_current_run = _selection_reason(
            included_in_current_run=included_in_current_run,
            eligible_for_property_discovery=eligible_for_property_discovery,
            excluded_by_legal_status=excluded_by_legal_status,
            excluded_by_missing_aanbod_url=excluded_by_missing_aanbod_url,
            unsupported_platform=unsupported_platform,
            included_by_override=included_by_override,
            previous_runs=previous_runs,
            is_active=is_active,
        )

        candidate_rows = current_candidates.get(source_domain, [])
        inventory_rows = current_inventory.get(source_domain, [])
        rejected_rows = current_rejected.get(source_domain, [])
        clean_available_rows = [row for row in inventory_rows if _is_clean_available(row)]
        invalid_address_count = sum(
            1
            for row in rejected_rows
            if (row.get("rejection_reason") or "") == "invalid_address_raw"
        )
        invalid_city_count = _count_invalid_city(inventory_rows) + sum(
            1 for row in rejected_rows if (row.get("rejection_reason") or "") == "invalid_city_raw"
        )
        invalid_price_count = _count_invalid_price(inventory_rows)
        unknown_status_count = _count_unknown_status(inventory_rows)
        needs_review_count = _count_needs_review(inventory_rows) + _count_needs_review(rejected_rows)
        sold_count = _count_status(inventory_rows, "verkocht", "sold")
        sold_ov_count = _count_status(inventory_rows, "verkocht_ov", "verkocht_onder_voorbehoud")
        onder_bod_count = _count_status(inventory_rows, "onder_bod")
        rejection_reasons = _rejection_counter(rejected_rows)
        review_reasons = _needs_review_counter(inventory_rows, rejected_rows)
        quality_score = _quality_score(
            candidates_found=len(candidate_rows),
            clean_available=len(clean_available_rows),
            rejected_candidates=len(rejected_rows),
            needs_review_count=needs_review_count,
            invalid_price_count=invalid_price_count,
            invalid_address_count=invalid_address_count,
            invalid_city_count=invalid_city_count,
            unknown_status_count=unknown_status_count,
        )
        recommended_action = _recommended_action(
            source_domain=source_domain,
            candidates_found=len(candidate_rows),
            rejected_candidates=len(rejected_rows),
            matching_ready=len(inventory_rows),
            clean_available=len(clean_available_rows),
            needs_review_count=needs_review_count,
            unknown_status_count=unknown_status_count,
            invalid_price_count=invalid_price_count,
            invalid_address_count=invalid_address_count,
            invalid_city_count=invalid_city_count,
            sold_count=sold_count,
            sold_ov_count=sold_ov_count,
            onder_bod_count=onder_bod_count,
        )

        target_city_rows = [row for row in inventory_rows if _city_matches_target(row.get("city_raw", ""), city)]
        outside_city_rows = [row for row in inventory_rows if row not in target_city_rows]
        target_city_clean_available = sum(1 for row in target_city_rows if _is_clean_available(row))
        outside_city_clean_available = sum(1 for row in outside_city_rows if _is_clean_available(row))
        target_city_unknown_status = _count_unknown_status(target_city_rows)
        target_city_invalid_price = _count_invalid_price(target_city_rows)
        invalid_city_for_filtering = _count_invalid_city(inventory_rows)
        can_support_city_specific_search = bool(target_city_rows or outside_city_rows) and invalid_city_for_filtering < max(
            2, len(inventory_rows)
        )
        filtering_risk = _filtering_risk(
            total_matching_ready=len(inventory_rows),
            properties_in_target_city=len(target_city_rows),
            outside_city_clean_available=outside_city_clean_available,
            invalid_city_count=invalid_city_for_filtering,
            target_city_unknown_status=target_city_unknown_status,
        )

        kin_current_run_status = ""
        kin_current_run_reason = ""
        if source_domain == "kinmakelaars.nl":
            kin_current_run_status = "included" if included_in_current_run else "not_included"
            kin_current_run_reason = reason_if_not_in_current_run

        output_rows.append(
            {
                "source_id": source_id,
                "office_name": (source_row.get("office_name") or "").strip(),
                "source_domain": source_domain,
                "city": (source_row.get("gemeente") or "").strip(),
                "province": (source_row.get("province") or source_row.get("provincie") or "").strip(),
                "detected_platform": detected_platform or "unknown",
                "supported_parser": _bool_str(supported_parser),
                "eligible_for_property_discovery": _bool_str(eligible_for_property_discovery),
                "included_in_current_run": _bool_str(included_in_current_run),
                "included_by_override": _bool_str(included_by_override),
                "included_in_baseline_or_previous_validated_run": _bool_str(included_in_baseline_or_previous_validated_run),
                "excluded_by_max_sources_or_priority": _bool_str(excluded_by_max_sources_or_priority),
                "excluded_by_legal_status": _bool_str(excluded_by_legal_status),
                "excluded_by_missing_aanbod_url": _bool_str(excluded_by_missing_aanbod_url),
                "unsupported_platform": _bool_str(unsupported_platform),
                "reason_if_not_in_current_run": reason_if_not_in_current_run,
                "kin_current_run_status": kin_current_run_status,
                "kin_current_run_reason": kin_current_run_reason,
                "candidates_found": str(len(candidate_rows)),
                "accepted_candidates": str(len(inventory_rows)),
                "rejected_candidates": str(len(rejected_rows)),
                "matching_ready": str(len(inventory_rows)),
                "clean_available": str(len(clean_available_rows)),
                "unknown_status_count": str(unknown_status_count),
                "invalid_price_count": str(invalid_price_count),
                "invalid_address_count": str(invalid_address_count),
                "invalid_city_count": str(invalid_city_count),
                "needs_review_count": str(needs_review_count),
                "sold_count": str(sold_count),
                "sold_ov_count": str(sold_ov_count),
                "onder_bod_count": str(onder_bod_count),
                "top_rejection_reasons": _counter_summary(rejection_reasons),
                "top_needs_review_reasons": _counter_summary(review_reasons),
                "quality_score": str(quality_score),
                "recommended_action": recommended_action,
                "total_matching_ready": str(len(inventory_rows)),
                "properties_in_target_city": str(len(target_city_rows)),
                "properties_outside_target_city": str(len(outside_city_rows)),
                "target_city_clean_available": str(target_city_clean_available),
                "outside_city_clean_available": str(outside_city_clean_available),
                "target_city_unknown_status": str(target_city_unknown_status),
                "target_city_invalid_price": str(target_city_invalid_price),
                "city_distribution_top_10": _city_distribution(inventory_rows),
                "can_support_city_specific_search": _bool_str(can_support_city_specific_search),
                "filtering_risk": filtering_risk,
            }
        )

    output_rows.sort(
        key=lambda row: (
            row["included_in_current_run"] != "true",
            row["source_domain"] != "kinmakelaars.nl",
            -int(row["clean_available"] or "0"),
            row["source_domain"],
        )
    )

    eligible_not_in_current = [
        row
        for row in output_rows
        if row["eligible_for_property_discovery"] == "true" and row["included_in_current_run"] == "false"
    ]
    quality_fix_needed = [
        row
        for row in output_rows
        if row["included_in_current_run"] == "true" and row["recommended_action"] != "keep_and_scale"
    ]
    if eligible_not_in_current and quality_fix_needed:
        recommended_decision = "mixed"
    elif eligible_not_in_current:
        recommended_decision = "add_next_supported_sources"
    else:
        recommended_decision = "fix_current_batch_quality"

    run_id = _utc_run_id()
    run_dir = output_base_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    inventory_path = run_dir / OUTPUT_INVENTORY_FILENAME
    report_path = run_dir / OUTPUT_REPORT_FILENAME
    _write_csv(inventory_path, output_rows)
    _write_markdown(
        report_path,
        _build_report(
            run_id=run_id,
            city=city,
            province=province,
            source_master_path=resolved_source_master_path,
            property_discovery_run_dir=resolved_run_dir,
            rows=output_rows,
            recommended_decision=recommended_decision,
        ),
    )
    return PropertyDiscoverySelectionQualityAuditResult(
        run_id=run_id,
        run_dir=run_dir,
        report_path=report_path,
        inventory_path=inventory_path,
        source_master_path=resolved_source_master_path,
        property_discovery_run_dir=resolved_run_dir,
        source_rows=output_rows,
        recommended_decision=recommended_decision,
    )
