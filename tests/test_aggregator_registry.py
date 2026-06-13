from pathlib import Path
import csv


def test_aggregator_registry_exists_and_adapters_are_disabled_by_default() -> None:
    path = Path(__file__).resolve().parents[1] / "data" / "discovery" / "reference" / "aggregator_legal_registry.csv"

    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows
    assert {row["aggregator_name"] for row in rows} >= {"Huispedia", "Huislijn", "Funda"}
    assert all((row["adapter_enabled"] or "").lower() == "false" for row in rows)
