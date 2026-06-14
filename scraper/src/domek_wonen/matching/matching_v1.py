from __future__ import annotations

import csv
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_RUNS_BASE_DIR = Path("data/property_discovery/runs")
DEFAULT_MATCHING_RUNS_DIR = Path("data/matching/runs")
DEFAULT_CLIENT_FIXTURE = Path("fixtures/matching/clients/laura_test_breda_001.json")
MATCHING_RESULTS_FILENAME = "matching_results.csv"
MATCHING_REPORT_FILENAME = "matching_report.md"

_NUMBER_RE = re.compile(r"(\d+)")
_CITY_COMPATIBILITY_MAP = {
    "breda": {"breda", "prinsenbeek", "ulvenhout", "bavel", "terheijden", "terheijden dorp"},
    "bergen op zoom": {"bergen op zoom", "halsteren"},
    "oosterhout": {"oosterhout", "dorst", "den hout"},
    "etten leur": {"etten leur", "etten", "leur"},
    "s hertogenbosch": {"s hertogenbosch", "den bosch", "rosmalen", "empel", "engelen"},
}


@dataclass(frozen=True)
class ClientProfile:
    client_id: str
    max_budget_eur: int
    preferred_cities: tuple[str, ...]
    min_rooms: int
    min_m2: int
    preferred_energy_labels: tuple[str, ...]
    wants_garden_or_balcony: bool
    language: str


@dataclass(frozen=True)
class MatchingRunResult:
    run_id: str
    run_dir: Path
    inventory_csv_path: Path
    inventory_run_id: str
    client_fixture_path: Path
    client_id: str
    total_inventory_rows: int
    total_clean_available: int
    total_hard_filter_passed: int
    results_path: Path
    report_path: Path
    top_matches: list[dict[str, str]]
    warning_counts: dict[str, int]


def load_client_profile(client_fixture_path: Path) -> ClientProfile:
    payload = json.loads(client_fixture_path.read_text(encoding="utf-8"))
    return ClientProfile(
        client_id=str(payload["client_id"]),
        max_budget_eur=int(payload["max_budget_eur"]),
        preferred_cities=tuple(str(value) for value in payload["preferred_cities"]),
        min_rooms=int(payload["min_rooms"]),
        min_m2=int(payload["min_m2"]),
        preferred_energy_labels=tuple(str(value).upper() for value in payload["preferred_energy_labels"]),
        wants_garden_or_balcony=bool(payload["wants_garden_or_balcony"]),
        language=str(payload["language"]),
    )


def find_latest_inventory_csv(runs_base_dir: Path = DEFAULT_RUNS_BASE_DIR) -> Path:
    run_dirs = sorted(path for path in runs_base_dir.iterdir() if path.is_dir())
    if not run_dirs:
        raise FileNotFoundError(f"No PropertyDiscovery runs found in {runs_base_dir}")

    latest_run_dir = run_dirs[-1]
    inventory_csv_path = latest_run_dir / "matching_ready_inventory.csv"
    if not inventory_csv_path.exists():
        raise FileNotFoundError(f"Missing matching_ready_inventory.csv in {latest_run_dir}")
    return inventory_csv_path


def run_matching_v1(
    inventory_csv_path: Path,
    client_fixture_path: Path = DEFAULT_CLIENT_FIXTURE,
    matching_runs_dir: Path = DEFAULT_MATCHING_RUNS_DIR,
) -> MatchingRunResult:
    client = load_client_profile(client_fixture_path)
    run_id = _utc_run_id()
    run_dir = matching_runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    with inventory_csv_path.open("r", encoding="utf-8", newline="") as handle:
        inventory_rows = list(csv.DictReader(handle))

    clean_available_rows = [row for row in inventory_rows if _is_clean_available(row)]

    scored_rows: list[dict[str, str]] = []
    warning_counts: dict[str, int] = {}
    for row in clean_available_rows:
        if not _passes_hard_filters(row, client):
            continue
        score, warnings = _score_row(row, client)
        for warning in warnings:
            warning_counts[warning] = warning_counts.get(warning, 0) + 1
        scored_rows.append(
            {
                "client_id": client.client_id,
                "property_id": row.get("property_id", ""),
                "address_raw": row.get("address_raw", ""),
                "city_raw": row.get("city_raw", ""),
                "price_eur": row.get("price_eur", ""),
                "score": str(score),
                "hard_filter_passed": "true",
                "warnings": "; ".join(warnings),
                "property_url": row.get("property_url", ""),
            }
        )

    scored_rows.sort(
        key=lambda row: (
            -int(row["score"]),
            _safe_int(row["price_eur"]) if row["price_eur"] else 10**12,
            row["property_id"],
        )
    )

    results_path = run_dir / MATCHING_RESULTS_FILENAME
    with results_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "client_id",
                "property_id",
                "address_raw",
                "city_raw",
                "price_eur",
                "score",
                "hard_filter_passed",
                "warnings",
                "property_url",
            ],
        )
        writer.writeheader()
        writer.writerows(scored_rows)

    report_path = run_dir / MATCHING_REPORT_FILENAME
    report_path.write_text(
        _build_report(
            run_id=run_id,
            inventory_csv_path=inventory_csv_path,
            client=client,
            total_clean_available=len(clean_available_rows),
            total_hard_filter_passed=len(scored_rows),
            top_matches=scored_rows[:10],
            warning_counts=warning_counts,
        ),
        encoding="utf-8",
    )

    return MatchingRunResult(
        run_id=run_id,
        run_dir=run_dir,
        inventory_csv_path=inventory_csv_path,
        inventory_run_id=inventory_csv_path.parent.name,
        client_fixture_path=client_fixture_path,
        client_id=client.client_id,
        total_inventory_rows=len(inventory_rows),
        total_clean_available=len(clean_available_rows),
        total_hard_filter_passed=len(scored_rows),
        results_path=results_path,
        report_path=report_path,
        top_matches=scored_rows[:10],
        warning_counts=warning_counts,
    )


def _is_clean_available(row: dict[str, str]) -> bool:
    return (
        row.get("status", "").strip().casefold() == "beschikbaar"
        and not _parse_bool(row.get("needs_review", ""))
        and row.get("address_quality", "").strip().casefold() == "valid"
        and _safe_int(row.get("price_eur", "")) is not None
    )


def _passes_hard_filters(row: dict[str, str], client: ClientProfile) -> bool:
    price_eur = _safe_int(row.get("price_eur", ""))
    if price_eur is None or price_eur > client.max_budget_eur:
        return False
    return _city_matches(row, client.preferred_cities)


def _score_row(row: dict[str, str], client: ClientProfile) -> tuple[int, list[str]]:
    warnings: list[str] = []
    score = 0.0

    price_eur = _safe_int(row.get("price_eur", "")) or client.max_budget_eur
    budget_ratio = max(0.0, min(1.0, (client.max_budget_eur - price_eur) / client.max_budget_eur))
    score += 20.0 + (budget_ratio * 10.0)

    if _city_matches(row, client.preferred_cities):
        score += 30.0

    rooms = _parse_optional_int(row.get("rooms")) or _parse_first_number(row.get("rooms_raw", ""))
    if rooms is None:
        warnings.append("missing_rooms")
    elif rooms >= client.min_rooms:
        score += 15.0

    living_area_m2 = _parse_optional_int(row.get("m2")) or _parse_first_number(row.get("living_area_raw", ""))
    if living_area_m2 is None:
        warnings.append("missing_m2")
    elif living_area_m2 >= client.min_m2:
        score += 15.0

    energy_label = row.get("energy_label", "").strip().upper()
    if not energy_label:
        warnings.append("missing_energy_label")
    elif energy_label in client.preferred_energy_labels:
        score += 10.0

    if client.wants_garden_or_balcony:
        outdoor_space = _detect_garden_or_balcony(row)
        if outdoor_space is None:
            warnings.append("missing_garden_or_balcony")
        elif outdoor_space:
            score += 10.0

    return max(0, min(100, round(score))), warnings


def _build_report(
    *,
    run_id: str,
    inventory_csv_path: Path,
    client: ClientProfile,
    total_clean_available: int,
    total_hard_filter_passed: int,
    top_matches: list[dict[str, str]],
    warning_counts: dict[str, int],
) -> str:
    top_lines = ["| # | property_id | city | price_eur | score | warnings | url |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for index, row in enumerate(top_matches, start=1):
        top_lines.append(
            "| {index} | {property_id} | {city} | {price} | {score} | {warnings} | {url} |".format(
                index=index,
                property_id=row["property_id"],
                city=row["city_raw"] or "-",
                price=row["price_eur"] or "-",
                score=row["score"],
                warnings=row["warnings"] or "-",
                url=row["property_url"] or "-",
            )
        )

    if len(top_lines) == 2:
        top_lines.append("| - | - | - | - | - | No matches | - |")

    warning_lines = ["- None"] if not warning_counts else [
        f"- {warning}: {count}" for warning, count in sorted(warning_counts.items(), key=lambda item: (-item[1], item[0]))
    ]

    score_lines = [
        "- Budget: 20-30 points, with higher score when the property stays further below the max budget.",
        "- Preferred city / simple compatible area: 30 points.",
        "- Rooms: 15 points if present and `>= min_rooms`; missing only adds a warning.",
        "- m2: 15 points if present and `>= min_m2`; missing only adds a warning.",
        "- Energy label: 10 points if present and preferred; missing only adds a warning.",
        "- Garden or balcony: 10 points if the signal exists and matches; missing only adds a warning.",
    ]

    return "\n".join(
        [
            "# Matching v1 Report",
            "",
            f"- Run timestamp: {run_id}",
            f"- Client fixture: {client.client_id}",
            f"- Inventory run used: {inventory_csv_path.parent.name}",
            f"- Inventory CSV: {inventory_csv_path}",
            f"- Total clean_available read: {total_clean_available}",
            f"- Total after hard filters: {total_hard_filter_passed}",
            "",
            "## Top 10 matches",
            *top_lines,
            "",
            "## Missing field warnings",
            *warning_lines,
            "",
            "## Score explanation",
            *score_lines,
            "",
        ]
    )


def _city_matches(row: dict[str, str], preferred_cities: tuple[str, ...]) -> bool:
    city_raw = _normalize_text(row.get("city_raw", ""))
    for preferred_city in preferred_cities:
        normalized_preferred = _normalize_text(preferred_city)
        if not normalized_preferred:
            continue
        compatible_cities = _CITY_COMPATIBILITY_MAP.get(normalized_preferred, {normalized_preferred})
        if city_raw in compatible_cities:
            return True
    return False


def _detect_garden_or_balcony(row: dict[str, str]) -> bool | None:
    for key in ("garden", "has_garden", "balcony", "has_balcony", "outdoor_space"):
        value = row.get(key, "")
        if value != "":
            return _parse_bool(value)

    haystack = " ".join(
        row.get(key, "")
        for key in ("features", "features_raw", "description", "description_raw", "title")
        if row.get(key, "")
    ).casefold()
    if not haystack:
        return None
    if any(keyword in haystack for keyword in ("garden", "tuin", "balkon", "balcony", "patio", "terrace", "terras")):
        return True
    return False


def _parse_bool(value: str) -> bool:
    return str(value).strip().casefold() in {"1", "true", "yes", "y"}


def _parse_optional_int(value: str | None) -> int | None:
    if value is None:
        return None
    stripped = str(value).strip()
    if not stripped:
        return None
    return _safe_int(stripped)


def _parse_first_number(value: str) -> int | None:
    match = _NUMBER_RE.search(value or "")
    if not match:
        return None
    return int(match.group(1))


def _safe_int(value: str | None) -> int | None:
    if value is None:
        return None
    digits = "".join(character for character in str(value) if character.isdigit())
    if not digits:
        return None
    return int(digits)


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = "".join(character for character in normalized if not unicodedata.combining(character))
    return " ".join(ascii_text.replace("-", " ").replace("'", "").split()).casefold()


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
