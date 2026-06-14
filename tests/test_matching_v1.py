from pathlib import Path
import csv
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.matching.matching_v1 import run_matching_v1


CLIENT_FIXTURE = Path("fixtures/matching/clients/client_test_brabant_001.json")
FIELDNAMES = [
    "property_id",
    "address_raw",
    "city_raw",
    "gemeente",
    "price_eur",
    "status",
    "needs_review",
    "address_quality",
    "rooms",
    "rooms_raw",
    "rooms_count",
    "bedrooms_count",
    "m2",
    "living_area_raw",
    "living_area_m2",
    "energy_label",
    "has_garden",
    "has_balcony",
    "property_url",
]


def _write_inventory_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _base_row(property_id: str, **overrides: str) -> dict[str, str]:
    row = {
        "property_id": property_id,
        "address_raw": f"Address {property_id}",
        "city_raw": "Breda",
        "gemeente": "Breda",
        "price_eur": "450000",
        "status": "beschikbaar",
        "needs_review": "false",
        "address_quality": "valid",
        "rooms": "4",
        "rooms_raw": "4 kamers",
        "rooms_count": "4",
        "bedrooms_count": "3",
        "m2": "95",
        "living_area_raw": "95 mÂ²",
        "living_area_m2": "95",
        "energy_label": "B",
        "has_garden": "true",
        "has_balcony": "",
        "property_url": f"https://example.nl/{property_id}",
    }
    row.update(overrides)
    return row


def test_matching_v1_applies_clean_available_filters_and_keeps_optional_missing_fields(tmp_path: Path) -> None:
    inventory_csv_path = tmp_path / "property_discovery" / "runs" / "20260614T184638Z" / "matching_ready_inventory.csv"
    _write_inventory_csv(
        inventory_csv_path,
        [
            _base_row("winner_missing_optional", rooms="", rooms_raw="", rooms_count="", m2="", living_area_raw="", living_area_m2="", energy_label="", has_garden="", has_balcony=""),
            _base_row("needs_review_row", needs_review="true"),
            _base_row("not_available_row", status="verkocht"),
            _base_row("bad_address_row", address_quality="invalid"),
            _base_row("too_expensive_row", price_eur="650000"),
        ],
    )

    result = run_matching_v1(
        inventory_csv_path=inventory_csv_path,
        client_fixture_path=CLIENT_FIXTURE,
        matching_runs_dir=tmp_path / "matching" / "runs",
    )

    with result.results_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    passed_rows = [row for row in rows if row["hard_filter_passed"] == "true"]
    assert result.total_clean_available == 2
    assert result.total_hard_filter_passed == 1
    assert result.exclusion_counts["excluded_over_budget"] == 1
    assert [row["property_id"] for row in passed_rows] == ["winner_missing_optional"]
    assert "missing_rooms" in passed_rows[0]["warnings"]
    assert "missing_m2" in passed_rows[0]["warnings"]
    assert "missing_energy_label" in passed_rows[0]["warnings"]


def test_matching_v1_allows_city_in_compatible_cities(tmp_path: Path) -> None:
    inventory_csv_path = tmp_path / "property_discovery" / "runs" / "20260614T184638Z" / "matching_ready_inventory.csv"
    _write_inventory_csv(
        inventory_csv_path,
        [
            _base_row(
                "halsteren_match",
                city_raw="Halsteren",
                gemeente="Bergen op Zoom",
                price_eur="430000",
            ),
        ],
    )

    result = run_matching_v1(
        inventory_csv_path=inventory_csv_path,
        client_fixture_path=CLIENT_FIXTURE,
        matching_runs_dir=tmp_path / "matching" / "runs",
    )

    with result.results_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert result.total_hard_filter_passed == 1
    assert rows[0]["property_id"] == "halsteren_match"
    assert rows[0]["hard_filter_passed"] == "true"


def test_matching_v1_orders_passed_results_by_score_descending(tmp_path: Path) -> None:
    inventory_csv_path = tmp_path / "property_discovery" / "runs" / "20260614T184638Z" / "matching_ready_inventory.csv"
    _write_inventory_csv(
        inventory_csv_path,
        [
            _base_row("strong_match", price_eur="320000", energy_label="A"),
            _base_row("weaker_match", price_eur="490000", rooms_count="3", m2="80", living_area_m2="80", energy_label="D"),
        ],
    )

    result = run_matching_v1(
        inventory_csv_path=inventory_csv_path,
        client_fixture_path=CLIENT_FIXTURE,
        matching_runs_dir=tmp_path / "matching" / "runs",
    )

    with result.results_path.open("r", encoding="utf-8", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if row["hard_filter_passed"] == "true"]

    scores = [int(row["score"]) for row in rows]
    assert [row["property_id"] for row in rows] == ["strong_match", "weaker_match"]
    assert scores == sorted(scores, reverse=True)


def test_matching_v1_excludes_bedrooms_below_minimum(tmp_path: Path) -> None:
    inventory_csv_path = tmp_path / "property_discovery" / "runs" / "20260614T184638Z" / "matching_ready_inventory.csv"
    _write_inventory_csv(
        inventory_csv_path,
        [
            _base_row("below_min_bedrooms", bedrooms_count="2", rooms_count="5", rooms_raw="5 kamers"),
        ],
    )

    result = run_matching_v1(
        inventory_csv_path=inventory_csv_path,
        client_fixture_path=CLIENT_FIXTURE,
        matching_runs_dir=tmp_path / "matching" / "runs",
    )

    with result.results_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert result.total_hard_filter_passed == 0
    assert rows[0]["property_id"] == "below_min_bedrooms"
    assert rows[0]["hard_filter_passed"] == "false"
    assert rows[0]["exclusion_reason"] == "excluded_bedrooms_below_min"


def test_matching_v1_excludes_missing_bedrooms_when_required(tmp_path: Path) -> None:
    inventory_csv_path = tmp_path / "property_discovery" / "runs" / "20260614T184638Z" / "matching_ready_inventory.csv"
    _write_inventory_csv(
        inventory_csv_path,
        [
            _base_row("missing_bedrooms", bedrooms_count="", rooms_count="4", rooms_raw="4 kamers"),
        ],
    )

    result = run_matching_v1(
        inventory_csv_path=inventory_csv_path,
        client_fixture_path=CLIENT_FIXTURE,
        matching_runs_dir=tmp_path / "matching" / "runs",
    )

    with result.results_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert result.total_hard_filter_passed == 0
    assert result.exclusion_counts["excluded_missing_bedrooms"] == 1
    assert rows[0]["hard_filter_passed"] == "false"
    assert rows[0]["exclusion_reason"] == "excluded_missing_bedrooms"


def test_matching_v1_excludes_city_outside_target_area(tmp_path: Path) -> None:
    inventory_csv_path = tmp_path / "property_discovery" / "runs" / "20260614T184638Z" / "matching_ready_inventory.csv"
    _write_inventory_csv(
        inventory_csv_path,
        [
            _base_row("outside_area", city_raw="Eindhoven", gemeente="Eindhoven"),
        ],
    )

    result = run_matching_v1(
        inventory_csv_path=inventory_csv_path,
        client_fixture_path=CLIENT_FIXTURE,
        matching_runs_dir=tmp_path / "matching" / "runs",
    )

    with result.results_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert result.total_hard_filter_passed == 0
    assert result.exclusion_counts["excluded_outside_target_area"] == 1
    assert rows[0]["exclusion_reason"] == "excluded_outside_target_area"


def test_matching_v1_preferred_cities_do_not_open_hard_filter(tmp_path: Path) -> None:
    inventory_csv_path = tmp_path / "property_discovery" / "runs" / "20260614T184638Z" / "matching_ready_inventory.csv"
    _write_inventory_csv(
        inventory_csv_path,
        [
            _base_row("preferred_not_target", city_raw="Etten-Leur", gemeente="Etten-Leur"),
        ],
    )

    result = run_matching_v1(
        inventory_csv_path=inventory_csv_path,
        client_fixture_path=CLIENT_FIXTURE,
        matching_runs_dir=tmp_path / "matching" / "runs",
    )

    with result.results_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert result.total_hard_filter_passed == 0
    assert rows[0]["exclusion_reason"] == "excluded_outside_target_area"
