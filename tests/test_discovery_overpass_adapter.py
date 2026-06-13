from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.discovery.overpass_adapter import OverpassAdapter


def test_overpass_parser_builds_source_candidates() -> None:
    payload = {
        "elements": [
            {
                "type": "node",
                "id": 101,
                "lat": 51.418,
                "lon": 5.406,
                "tags": {
                    "name": "Alpha Makelaardij",
                    "website": "https://www.alpha.nl",
                    "addr:city": "Veldhoven",
                    "addr:postcode": "5501AA",
                    "phone": "+31 40 123 4567",
                    "email": "info@alpha.nl",
                },
            },
            {
                "type": "node",
                "id": 202,
                "center": {"lat": 51.35, "lon": 5.46},
                "tags": {
                    "name": "Beta Vastgoed",
                    "addr:city": "Bavel",
                },
            },
        ]
    }

    adapter = OverpassAdapter(sleep_func=lambda _: None)
    candidates = adapter._parse_candidates(payload)

    assert len(candidates) == 2

    with_website = candidates[0]
    assert with_website.office_name == "Alpha Makelaardij"
    assert with_website.website == "https://www.alpha.nl"
    assert with_website.root_domain == "alpha.nl"
    assert with_website.raw_place == "Veldhoven"
    assert with_website.normalized_place == "Veldhoven"
    assert with_website.gemeente == "Veldhoven"
    assert with_website.plaats == "Veldhoven"
    assert with_website.place_status == "current_gemeente"
    assert with_website.provincie == "Noord-Brabant"
    assert with_website.source_origin == "overpass_osm"
    assert with_website.needs_review is True
    assert with_website.confidence == 0.50
    assert with_website.osm_id == "101"
    assert with_website.osm_lat == "51.418"
    assert with_website.osm_lon == "5.406"

    without_website = candidates[1]
    assert without_website.office_name == "Beta Vastgoed"
    assert without_website.website == ""
    assert without_website.root_domain == ""
    assert without_website.raw_place == "Bavel"
    assert without_website.normalized_place == "Bavel"
    assert without_website.gemeente == "Breda"
    assert without_website.plaats == "Bavel"
    assert without_website.place_status == "locality_to_gemeente"
    assert without_website.osm_lat == "51.35"
    assert without_website.osm_lon == "5.46"
