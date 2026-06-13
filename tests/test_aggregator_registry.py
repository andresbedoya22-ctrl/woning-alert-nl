from pathlib import Path
import csv


def test_aggregator_registry_exists_and_adapters_are_disabled_by_default() -> None:
    path = Path(__file__).resolve().parents[1] / "data" / "discovery" / "reference" / "aggregator_legal_registry.csv"

    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows
    assert {row["aggregator_name"] for row in rows} >= {"Huispedia", "Huislijn", "Funda"}
    assert all((row["adapter_enabled"] or "").lower() == "false" for row in rows)
    assert any(row["aggregator_name"] == "Huispedia" and row["base_url"] == "https://huispedia.nl/" for row in rows)
    assert any(row["aggregator_name"] == "Funda" and row["permission_status"] == "not_allowed_for_scraping" for row in rows)
