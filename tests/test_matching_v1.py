from pathlib import Path
import csv
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.matching.matching_v1 import run_matching_v1


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
    "m2",
    "living_area_raw",
    "energy_label",
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
        "m2": "95",
        "living_area_raw": "95 m²",
        "energy_label": "B",
        "property_url": f"https://example.nl/{property_id}",
    }
    row.update(overrides)
    return row


def test_matching_v1_applies_clean_available_filters_and_keeps_optional_missing_fields(tmp_path: Path) -> None:
    inventory_csv_path = tmp_path / "property_discovery" / "runs" / "20260614T184638Z" / "matching_ready_inventory.csv"
    _write_inventory_csv(
        inventory_csv_path,
        [
            _base_row("winner_missing_optional", rooms="", rooms_raw="", m2="", living_area_raw="", energy_label=""),
            _base_row("needs_review_row", needs_review="true"),
            _base_row("not_available_row", status="verkocht"),
            _base_row("bad_address_row", address_quality="invalid"),
            _base_row("too_expensive_row", price_eur="650000"),
        ],
    )

    result = run_matching_v1(
        inventory_csv_path=inventory_csv_path,
        client_fixture_path=Path("fixtures/matching/clients/laura_test_breda_001.json"),
        matching_runs_dir=tmp_path / "matching" / "runs",
    )

    with result.results_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert result.total_clean_available == 2
    assert result.total_hard_filter_passed == 1
    assert [row["property_id"] for row in rows] == ["winner_missing_optional"]
    assert "missing_rooms" in rows[0]["warnings"]
    assert "missing_m2" in rows[0]["warnings"]
    assert "missing_energy_label" in rows[0]["warnings"]


def test_matching_v1_supports_simple_gemeente_compatibility(tmp_path: Path) -> None:
    inventory_csv_path = tmp_path / "property_discovery" / "runs" / "20260614T184638Z" / "matching_ready_inventory.csv"
    _write_inventory_csv(
        inventory_csv_path,
        [
            _base_row(
                "rosmalen_match",
                city_raw="Rosmalen",
                gemeente="'s-Hertogenbosch",
                price_eur="430000",
            ),
        ],
    )

    result = run_matching_v1(
        inventory_csv_path=inventory_csv_path,
        client_fixture_path=Path("fixtures/matching/clients/laura_test_breda_001.json"),
        matching_runs_dir=tmp_path / "matching" / "runs",
    )

    with result.results_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert result.total_hard_filter_passed == 1
    assert rows[0]["property_id"] == "rosmalen_match"


def test_matching_v1_orders_results_by_score_descending(tmp_path: Path) -> None:
    inventory_csv_path = tmp_path / "property_discovery" / "runs" / "20260614T184638Z" / "matching_ready_inventory.csv"
    _write_inventory_csv(
        inventory_csv_path,
        [
            _base_row("strong_match", price_eur="320000", energy_label="A"),
            _base_row("weaker_match", price_eur="490000", rooms="3", m2="80", energy_label="D"),
        ],
    )

    result = run_matching_v1(
        inventory_csv_path=inventory_csv_path,
        client_fixture_path=Path("fixtures/matching/clients/laura_test_breda_001.json"),
        matching_runs_dir=tmp_path / "matching" / "runs",
    )

    with result.results_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    scores = [int(row["score"]) for row in rows]
    assert [row["property_id"] for row in rows] == ["strong_match", "weaker_match"]
    assert scores == sorted(scores, reverse=True)
