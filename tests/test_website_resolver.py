from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.discovery.models import SourceCandidate
from domek_wonen.discovery.website_resolver import resolve_websites


def test_fuzzy_match_resolves_website_from_seed() -> None:
    unresolved = [
        SourceCandidate(
            office_name="Alpha Makelaars BV",
            gemeente="Breda",
            plaats="Breda",
            source_origin="overpass_osm",
        )
    ]
    seed = [
        SourceCandidate(
            office_name="Alpha Makelaardij",
            website="https://www.alpha.nl",
            root_domain="alpha.nl",
            gemeente="Breda",
            plaats="Breda",
        )
    ]

    result = resolve_websites(unresolved, seed_candidates=seed)

    assert len(result.resolved_candidates) == 1
    assert result.resolved_candidates[0].website == "https://www.alpha.nl"
    assert result.resolved_candidates[0].website_resolution_status == "resolved_seed_match"
    assert result.manual_review_rows == []


def test_missing_website_goes_to_manual_review_when_no_match() -> None:
    unresolved = [
        SourceCandidate(
            office_name="Unknown Wonen",
            gemeente="Breda",
            plaats="Breda",
            source_origin="overpass_osm",
            raw_place="Breda",
            normalized_place="Breda",
            osm_phone="+31 10 000 0000",
            osm_email="unknown@example.nl",
            osm_lat="51.0",
            osm_lon="4.0",
        )
    ]

    result = resolve_websites(unresolved, seed_candidates=[])

    assert len(result.unresolved_candidates) == 1
    assert result.unresolved_candidates[0].website_resolution_status == "needs_manual_review"
    assert len(result.manual_review_rows) == 1
    assert result.manual_review_rows[0]["reason"] == "missing_website_unresolved"
