from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from domek_wonen.discovery.discovery_artifacts import resolve_makelaar_sources_master
from domek_wonen.discovery.platform_fingerprint import detect_target_platform_from_text
from domek_wonen.properties.platform_parser_registry import get_platform_parser


DEFAULT_OUTPUT_BASE_DIR = Path("data/diagnostics/source_coverage")
DEFAULT_PLATFORM_FINGERPRINT_PATH = Path("data/discovery/platform_fingerprint/platform_fingerprint_results.csv")
DEFAULT_DISCOVERY_RUNS_DIR = Path("data/discovery/runs")
DEFAULT_PROPERTY_DISCOVERY_RUNS_DIR = Path("data/property_discovery/runs")
INVENTORY_FILENAME = "tilburg_source_coverage_inventory.csv"
REPORT_FILENAME = "tilburg_source_coverage_report.md"
CSV_FIELDNAMES = [
    "source_name",
    "source_domain",
    "city",
    "province",
    "platform_guess",
    "platform_confidence",
    "operational_status",
    "supported_by_existing_parser",
    "included_in_discovery",
    "last_seen_or_run",
    "evidence",
    "notes",
]
ALLOWED_PLATFORM_GUESSES = {
    "realworks",
    "ogonline",
    "kolibri",
    "skarabee",
    "pyber",
    "yes-co",
    "custom",
    "unknown",
    "missing_input",
}


@dataclass(frozen=True)
class SourceCoverageRunResult:
    run_id: str
    run_dir: Path
    source_master_path: Path | None
    platform_fingerprint_path: Path | None
    property_discovery_run_dir: Path | None
    report_path: Path
    inventory_output_path: Path
    total_sources_for_city: int
    supported_sources: int
    unsupported_sources: int
    unknown_platform_sources: int
    timeout_or_blocked_sources: int
    duplicate_sources: int
    sources_in_discovery: int
    sources_not_in_discovery: int
    supported_not_in_discovery: int
    recommended_next_bottleneck: str
    inventory_rows: list[dict[str, str]]


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _normalize_text(value: str) -> str:
    return " ".join((value or "").strip().lower().replace("_", " ").split())


def _normalize_city(value: str) -> str:
    return _normalize_text(value)


def _normalize_province(value: str) -> str:
    return _normalize_text(value).replace("-", " ")


def _bool_str(value: bool) -> str:
    return "true" if value else "false"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_csv_if_exists(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
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


def _existing_path(path: Path) -> Path | None:
    return path if path.exists() else None


def _resolve_source_master_path(path: Path | None) -> Path | None:
    if path is not None:
        return _existing_path(path)
    try:
        return resolve_makelaar_sources_master(input_path=None, restore_latest=False)
    except FileNotFoundError:
        return None


def _resolve_platform_fingerprint_path(path: Path | None) -> Path | None:
    return _existing_path(path or DEFAULT_PLATFORM_FINGERPRINT_PATH)


def _resolve_latest_property_discovery_run_dir(runs_dir: Path) -> Path | None:
    if not runs_dir.exists():
        return None
    valid_runs = [
        candidate
        for candidate in runs_dir.iterdir()
        if candidate.is_dir()
        and any(
            (candidate / filename).exists()
            for filename in ("property_candidates.csv", "property_rejected.csv", "matching_ready_inventory.csv")
        )
    ]
    if not valid_runs:
        return None
    return sorted(valid_runs, key=lambda item: item.name, reverse=True)[0]


def _extract_domain(*values: str) -> str:
    for value in values:
        raw = (value or "").strip()
        if not raw:
            continue
        parsed = urlsplit(raw if "://" in raw else f"https://{raw}")
        hostname = parsed.netloc or parsed.path
        hostname = hostname.lower().strip().strip("/")
        if hostname.startswith("www."):
            hostname = hostname[4:]
        if hostname:
            return hostname
    return ""


def _index_fingerprint_rows(rows: list[dict[str, str]]) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    by_source_id: dict[str, dict[str, str]] = {}
    by_domain: dict[str, dict[str, str]] = {}
    for row in rows:
        source_id = (row.get("source_id") or "").strip().lower()
        domain = _extract_domain(row.get("root_domain", ""), row.get("website_url", ""), row.get("aanbod_url", ""))
        if source_id and source_id not in by_source_id:
            by_source_id[source_id] = row
        if domain and domain not in by_domain:
            by_domain[domain] = row
    return by_source_id, by_domain


def _normalize_platform_guess(raw_platform: str) -> str:
    platform = (raw_platform or "").strip().lower()
    mapping = {
        "realworks": "realworks",
        "ogonline_candidate": "ogonline",
        "ogonline": "ogonline",
        "kolibri": "kolibri",
        "skarabee": "skarabee",
        "pyber": "pyber",
        "yes-co": "yes-co",
        "yesco": "yes-co",
        "wordpress_makelaar_plugin": "custom",
        "pararius_office": "custom",
        "osre": "custom",
        "tiara": "custom",
        "custom": "custom",
        "unknown": "unknown",
        "": "missing_input",
    }
    normalized = mapping.get(platform, "custom")
    return normalized if normalized in ALLOWED_PLATFORM_GUESSES else "custom"


def _platform_guess_from_rows(
    source_row: dict[str, str],
    fingerprint_row: dict[str, str] | None,
) -> tuple[str, str, list[str]]:
    if fingerprint_row is not None:
        platform = _normalize_platform_guess(fingerprint_row.get("detected_platform", ""))
        confidence = fingerprint_row.get("confidence") or fingerprint_row.get("confidence_score") or ""
        evidence = [
            f"platform_fingerprint:{fingerprint_row.get('detected_platform', '').strip() or 'missing_input'}",
        ]
        for key in ("evidence", "fetch_status", "error", "detection_reasons"):
            value = (fingerprint_row.get(key) or "").strip()
            if value:
                evidence.append(f"{key}:{value}")
        return platform, confidence or ("0.20" if platform == "unknown" else ""), evidence

    website_url = source_row.get("website") or source_row.get("website_url") or ""
    aanbod_url = source_row.get("aanbod_url") or ""
    if website_url or aanbod_url:
        detected_platform, confidence, reasons = detect_target_platform_from_text(
            "",
            "",
            website_url=website_url,
            aanbod_url=aanbod_url,
        )
        normalized = _normalize_platform_guess(detected_platform)
        evidence = [f"url_heuristic:{detected_platform or 'missing_input'}"]
        evidence.extend(reasons[:6])
        return normalized, f"{confidence:.2f}", evidence

    return "missing_input", "", ["missing_input:no_platform_evidence"]


def _load_property_discovery_presence(
    run_dir: Path | None,
) -> tuple[set[str], dict[str, str]]:
    if run_dir is None:
        return set(), {}

    seen_domains: set[str] = set()
    last_seen_by_domain: dict[str, str] = {}
    candidate_paths = [
        run_dir / "property_candidates.csv",
        run_dir / "property_rejected.csv",
        run_dir / "matching_ready_inventory.csv",
    ]
    for path in candidate_paths:
        for row in _read_csv_if_exists(path):
            domain = _extract_domain(
                row.get("root_domain", ""),
                row.get("source_root_domain", ""),
                row.get("source_url", ""),
                row.get("source_aanbod_url", ""),
            )
            if not domain:
                continue
            seen_domains.add(domain)
            last_seen = (
                row.get("discovery_run_id")
                or row.get("last_seen_at")
                or row.get("first_seen_at")
                or run_dir.name
            )
            if last_seen:
                last_seen_by_domain[domain] = last_seen
    return seen_domains, last_seen_by_domain


def _build_operational_status(
    *,
    source_domain: str,
    duplicate_domains: set[str],
    platform_guess: str,
    supported_by_existing_parser: bool,
    evidence_blob: str,
    website_url: str,
    aanbod_url: str,
) -> str:
    evidence_lower = evidence_blob.lower()
    if source_domain and source_domain in duplicate_domains:
        return "duplicate"
    if "timeout" in evidence_lower or "timed out" in evidence_lower:
        return "timeout"
    if "blocked" in evidence_lower:
        return "blocked"
    if platform_guess == "missing_input" and not website_url and not aanbod_url:
        return "missing_input"
    if supported_by_existing_parser:
        return "supported"
    if platform_guess == "unknown":
        return "unknown"
    if platform_guess == "missing_input":
        return "missing_input"
    return "unsupported"


def _build_notes(
    *,
    source_row: dict[str, str],
    fingerprint_row: dict[str, str] | None,
    platform_guess: str,
    supported_by_existing_parser: bool,
    included_in_discovery: bool,
    operational_status: str,
) -> str:
    notes: list[str] = []
    legal_status = (source_row.get("legal_status") or "").strip()
    if legal_status:
        notes.append(f"legal_status={legal_status}")
    if fingerprint_row is None:
        notes.append("platform_fingerprint=missing_input")
    if not included_in_discovery:
        notes.append("not_seen_in_property_discovery")
    if platform_guess in {"unknown", "missing_input"}:
        notes.append("platform_needs_more_evidence")
    if platform_guess not in {"unknown", "missing_input"} and not supported_by_existing_parser:
        notes.append("known_platform_without_existing_parser")
    if operational_status in {"timeout", "blocked"}:
        notes.append("operational_gap_for_coverage")
    return "; ".join(notes)


def _top_counter_items(counter: Counter[str], *, limit: int = 5) -> str:
    if not counter:
        return "none"
    return ", ".join(f"{name} ({count})" for name, count in counter.most_common(limit))


def _recommended_next_bottleneck(
    rows: list[dict[str, str]],
    *,
    supported_not_in_discovery_count: int,
) -> str:
    counts = Counter(row["operational_status"] for row in rows)
    unsupported_platform_counts = Counter(
        row["platform_guess"]
        for row in rows
        if row["operational_status"] == "unsupported" and row["platform_guess"] not in {"unknown", "missing_input"}
    )
    if supported_not_in_discovery_count > 0:
        return "add_supported_source_to_discovery"
    if counts.get("unknown", 0) > 0 or counts.get("missing_input", 0) > 0:
        return "investigate_unknown_platform"
    if unsupported_platform_counts:
        return "investigate_unsupported_platform"
    if counts.get("duplicate", 0) > 0:
        return "dedupe_duplicate_sources"
    return "improve_existing_source_recovery"


def _build_report(
    *,
    run_id: str,
    city: str,
    province: str,
    inventory_rows: list[dict[str, str]],
    source_master_path: Path | None,
    platform_fingerprint_path: Path | None,
    property_discovery_run_dir: Path | None,
    recommended_next_bottleneck: str,
) -> str:
    status_counts = Counter(row["operational_status"] for row in inventory_rows)
    platform_counts = Counter(row["platform_guess"] for row in inventory_rows)
    supported_not_in_discovery = [
        row for row in inventory_rows if row["operational_status"] == "supported" and row["included_in_discovery"] == "false"
    ]
    supported_not_in_discovery_count = len(supported_not_in_discovery)
    top_gaps = Counter()
    for row in inventory_rows:
        if row["operational_status"] in {"unsupported", "unknown", "missing_input", "timeout", "blocked", "duplicate"}:
            top_gaps[row["source_domain"] or row["source_name"]] += 1

    explanation = (
        "This report is a local source-coverage diagnostic built only from existing source master, "
        "platform fingerprint, and PropertyDiscovery artifacts. It highlights sources that are absent "
        "from PropertyDiscovery, have no supported parser, or lack enough local evidence to explain Tilburg coverage gaps."
    )

    lines = [
        "# Tilburg Source Coverage Report v1",
        "",
        f"- run_timestamp: {run_id}",
        f"- city: {city}",
        f"- province: {province}",
        f"- source_master_path: {source_master_path or 'missing_input'}",
        f"- platform_fingerprint_path: {platform_fingerprint_path or 'missing_input'}",
        f"- property_discovery_run_dir: {property_discovery_run_dir or 'missing_input'}",
        "",
        "## Summary",
        f"- city: {city}",
        f"- province: {province}",
        f"- total_sources_for_city: {len(inventory_rows)}",
        f"- supported_sources: {status_counts.get('supported', 0)}",
        f"- unsupported_sources: {status_counts.get('unsupported', 0)}",
        f"- unknown_platform_sources: {platform_counts.get('unknown', 0) + platform_counts.get('missing_input', 0)}",
        f"- timeout_or_blocked_sources: {status_counts.get('timeout', 0) + status_counts.get('blocked', 0)}",
        f"- duplicate_sources: {status_counts.get('duplicate', 0)}",
        f"- sources_in_discovery: {sum(1 for row in inventory_rows if row['included_in_discovery'] == 'true')}",
        f"- sources_not_in_discovery: {sum(1 for row in inventory_rows if row['included_in_discovery'] == 'false')}",
        f"- supported_not_in_discovery: {supported_not_in_discovery_count}",
        f"- top_platforms: {_top_counter_items(platform_counts)}",
        f"- top_operational_gaps: {_top_counter_items(top_gaps)}",
        f"- recommended_next_bottleneck: {recommended_next_bottleneck}",
        f"- explanation: {explanation}",
        "",
        "## Supported But Not In Discovery",
    ]
    if supported_not_in_discovery:
        for row in supported_not_in_discovery[:10]:
            lines.append(f"- {row['source_name']} [{row['source_domain']}]")
    else:
        lines.append("- none")

    lines.extend(["", "## Top Tilburg Sources"])
    sorted_rows = sorted(
        inventory_rows,
        key=lambda row: (
            row["operational_status"] != "supported",
            row["included_in_discovery"] != "true",
            row["source_name"].lower(),
        ),
    )
    for row in sorted_rows[:10]:
        lines.append(
            f"- {row['source_name']} | {row['source_domain']} | {row['platform_guess']} | "
            f"{row['operational_status']} | included_in_discovery={row['included_in_discovery']}"
        )
    return "\n".join(lines) + "\n"


def run_source_coverage_map(
    *,
    city: str,
    province: str,
    source_master_path: Path | None = None,
    platform_fingerprint_path: Path | None = None,
    property_discovery_run_dir: Path | None = None,
    output_base_dir: Path = DEFAULT_OUTPUT_BASE_DIR,
) -> SourceCoverageRunResult:
    resolved_source_master_path = _resolve_source_master_path(source_master_path)
    resolved_platform_fingerprint_path = _resolve_platform_fingerprint_path(platform_fingerprint_path)
    resolved_property_discovery_run_dir = property_discovery_run_dir or _resolve_latest_property_discovery_run_dir(
        DEFAULT_PROPERTY_DISCOVERY_RUNS_DIR
    )

    source_rows = _read_csv_if_exists(resolved_source_master_path)
    fingerprint_rows = _read_csv_if_exists(resolved_platform_fingerprint_path)
    fingerprint_by_source_id, fingerprint_by_domain = _index_fingerprint_rows(fingerprint_rows)
    included_domains, last_seen_by_domain = _load_property_discovery_presence(resolved_property_discovery_run_dir)

    normalized_city = _normalize_city(city)
    normalized_province = _normalize_province(province)
    filtered_source_rows = [
        row
        for row in source_rows
        if _normalize_city(row.get("gemeente", "")) == normalized_city
        and _normalize_province(row.get("province", "") or row.get("provincie", "")) == normalized_province
    ]

    domain_counts = Counter(
        _extract_domain(row.get("root_domain", ""), row.get("website", ""), row.get("aanbod_url", ""))
        for row in filtered_source_rows
    )
    duplicate_domains = {domain for domain, count in domain_counts.items() if domain and count > 1}

    inventory_rows: list[dict[str, str]] = []
    for source_row in filtered_source_rows:
        source_name = (source_row.get("office_name") or "").strip() or "missing_input"
        source_domain = _extract_domain(
            source_row.get("root_domain", ""),
            source_row.get("website", ""),
            source_row.get("aanbod_url", ""),
        )
        source_id = (source_row.get("source_id") or "").strip().lower()
        fingerprint_row = None
        if source_id:
            fingerprint_row = fingerprint_by_source_id.get(source_id)
        if fingerprint_row is None and source_domain:
            fingerprint_row = fingerprint_by_domain.get(source_domain)

        platform_guess, platform_confidence, evidence_parts = _platform_guess_from_rows(source_row, fingerprint_row)
        supported_by_existing_parser = get_platform_parser(platform_guess) is not None
        included_in_discovery = source_domain in included_domains if source_domain else False
        last_seen_or_run = (
            last_seen_by_domain.get(source_domain, "")
            or (source_row.get("last_seen_at") or "").strip()
            or (source_row.get("run_id") or "").strip()
            or (resolved_property_discovery_run_dir.name if included_in_discovery and resolved_property_discovery_run_dir else "")
            or "missing_input"
        )
        evidence_blob = " | ".join(part for part in evidence_parts if part)
        operational_status = _build_operational_status(
            source_domain=source_domain,
            duplicate_domains=duplicate_domains,
            platform_guess=platform_guess,
            supported_by_existing_parser=supported_by_existing_parser,
            evidence_blob=evidence_blob,
            website_url=source_row.get("website", ""),
            aanbod_url=source_row.get("aanbod_url", ""),
        )
        notes = _build_notes(
            source_row=source_row,
            fingerprint_row=fingerprint_row,
            platform_guess=platform_guess,
            supported_by_existing_parser=supported_by_existing_parser,
            included_in_discovery=included_in_discovery,
            operational_status=operational_status,
        )
        inventory_rows.append(
            {
                "source_name": source_name,
                "source_domain": source_domain or "missing_input",
                "city": source_row.get("gemeente", "") or city,
                "province": source_row.get("province", "") or source_row.get("provincie", "") or province,
                "platform_guess": platform_guess,
                "platform_confidence": platform_confidence or "missing_input",
                "operational_status": operational_status,
                "supported_by_existing_parser": _bool_str(supported_by_existing_parser),
                "included_in_discovery": _bool_str(included_in_discovery),
                "last_seen_or_run": last_seen_or_run,
                "evidence": evidence_blob or "missing_input",
                "notes": notes or "",
            }
        )

    inventory_rows.sort(
        key=lambda row: (
            row["operational_status"] != "supported",
            row["included_in_discovery"] != "true",
            row["source_name"].lower(),
        )
    )

    supported_not_in_discovery_count = sum(
        1
        for row in inventory_rows
        if row["operational_status"] == "supported" and row["included_in_discovery"] == "false"
    )
    recommended_next_bottleneck = _recommended_next_bottleneck(
        inventory_rows,
        supported_not_in_discovery_count=supported_not_in_discovery_count,
    )

    run_id = _utc_run_id()
    run_dir = output_base_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    inventory_output_path = run_dir / INVENTORY_FILENAME
    report_path = run_dir / REPORT_FILENAME
    _write_csv(inventory_output_path, inventory_rows)
    _write_markdown(
        report_path,
        _build_report(
            run_id=run_id,
            city=city,
            province=province,
            inventory_rows=inventory_rows,
            source_master_path=resolved_source_master_path,
            platform_fingerprint_path=resolved_platform_fingerprint_path,
            property_discovery_run_dir=resolved_property_discovery_run_dir,
            recommended_next_bottleneck=recommended_next_bottleneck,
        ),
    )

    return SourceCoverageRunResult(
        run_id=run_id,
        run_dir=run_dir,
        source_master_path=resolved_source_master_path,
        platform_fingerprint_path=resolved_platform_fingerprint_path,
        property_discovery_run_dir=resolved_property_discovery_run_dir,
        report_path=report_path,
        inventory_output_path=inventory_output_path,
        total_sources_for_city=len(inventory_rows),
        supported_sources=sum(1 for row in inventory_rows if row["operational_status"] == "supported"),
        unsupported_sources=sum(1 for row in inventory_rows if row["operational_status"] == "unsupported"),
        unknown_platform_sources=sum(
            1 for row in inventory_rows if row["platform_guess"] in {"unknown", "missing_input"}
        ),
        timeout_or_blocked_sources=sum(
            1 for row in inventory_rows if row["operational_status"] in {"timeout", "blocked"}
        ),
        duplicate_sources=sum(1 for row in inventory_rows if row["operational_status"] == "duplicate"),
        sources_in_discovery=sum(1 for row in inventory_rows if row["included_in_discovery"] == "true"),
        sources_not_in_discovery=sum(1 for row in inventory_rows if row["included_in_discovery"] == "false"),
        supported_not_in_discovery=supported_not_in_discovery_count,
        recommended_next_bottleneck=recommended_next_bottleneck,
        inventory_rows=inventory_rows,
    )
