from pathlib import Path
import sys
import json

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


def test_overpass_uses_cache_when_mirrors_fail(tmp_path) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "overpass_noord-brabant_latest.json").write_text(
        json.dumps(
            {
                "elements": [
                    {
                        "type": "node",
                        "id": 1,
                        "tags": {"name": "Cached Makelaar", "website": "https://cached.example.nl", "addr:city": "Breda"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (cache_dir / "overpass_noord-brabant_latest_meta.json").write_text(
        json.dumps({"timestamp": "2026-06-13T00:00:00Z", "source": "primary", "mirror_used": "cached"}),
        encoding="utf-8",
    )

    adapter = OverpassAdapter(cache_dir=cache_dir, sleep_func=lambda _: None)
    adapter._post_query = lambda url, query: (_ for _ in ()).throw(RuntimeError("mirror down"))  # type: ignore[method-assign]

    response = adapter.discover("Noord-Brabant")

    assert response.status == "ok_cached"
    assert response.cache_used is True
    assert response.cache_timestamp == "2026-06-13T00:00:00Z"
    assert response.source_label == "cache"
    assert response.raw_candidates == 1
