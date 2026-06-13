from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.discovery.place_mapper import normalize_overpass_city


def test_normalize_overpass_city_maps_localities_and_former_gemeenten() -> None:
    assert normalize_overpass_city("Bavel")["gemeente"] == "Breda"
    assert normalize_overpass_city("Rosmalen")["gemeente"] == "'s-Hertogenbosch"
    assert normalize_overpass_city("Uden")["gemeente"] == "Maashorst"
    assert normalize_overpass_city("Cuijk")["gemeente"] == "Land van Cuijk"


def test_normalize_overpass_city_keeps_current_gemeente() -> None:
    mapped = normalize_overpass_city("Veldhoven")
    assert mapped["normalized_place"] == "Veldhoven"
    assert mapped["gemeente"] == "Veldhoven"
    assert mapped["place_status"] == "current_gemeente"


def test_normalize_overpass_city_unknown_or_empty_goes_to_unknown() -> None:
    empty = normalize_overpass_city("")
    assert empty["normalized_place"] == "(unknown)"
    assert empty["gemeente"] == "(unknown)"
    assert empty["place_status"] == "needs_review"

    unknown = normalize_overpass_city("Onbekend Dorp")
    assert unknown["normalized_place"] == "(unknown)"
    assert unknown["gemeente"] == "(unknown)"
    assert unknown["place_status"] == "needs_review"
