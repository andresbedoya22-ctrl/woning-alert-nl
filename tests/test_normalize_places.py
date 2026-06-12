from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.normalize_places import enrich_source_rows, resolve_place


def test_resolve_place_handles_known_alias_and_former_gemeente() -> None:
    assert resolve_place("Landerd") == {
        "raw_place": "Landerd",
        "normalized_place": "Maashorst",
        "gemeente": "Maashorst",
        "status": "former_gemeente",
        "notes": "Former municipality merged into Maashorst.",
    }
    assert resolve_place("Den Bosch")["gemeente"] == "'s-Hertogenbosch"
    assert resolve_place("Den Bosch")["status"] == "alias"


def test_resolve_place_handles_format_aliases() -> None:
    assert resolve_place("Bergen Op Zoom")["normalized_place"] == "Bergen op Zoom"
    assert resolve_place("Nuenen Gerwen En Nederwetten")["gemeente"] == "Nuenen, Gerwen en Nederwetten"
    assert resolve_place("Breda")["status"] == "current_gemeente"


def test_enrich_source_rows_appends_required_columns() -> None:
    enriched_rows, place_map_rows = enrich_source_rows(
        [
            {"plaats": "Landerd", "office_name": "A"},
            {"plaats": "Breda", "office_name": "B"},
        ]
    )

    assert enriched_rows[0]["raw_place"] == "Landerd"
    assert enriched_rows[0]["gemeente"] == "Maashorst"
    assert enriched_rows[0]["place_status"] == "former_gemeente"
    assert enriched_rows[0]["place_review_reason"] == ""
    assert enriched_rows[1]["normalized_place"] == "Breda"
    assert place_map_rows[0]["raw_place"] == "Breda"
    assert place_map_rows[1]["raw_place"] == "Landerd"
