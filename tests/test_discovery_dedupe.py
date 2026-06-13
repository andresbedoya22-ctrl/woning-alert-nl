from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.discovery.dedupe import dedupe_candidates
from domek_wonen.discovery.models import SourceCandidate


def test_dedupe_eliminates_duplicate_by_root_domain_and_gemeente() -> None:
    candidates = [
        SourceCandidate(
            office_name="Example Makelaar",
            website="https://example.nl",
            root_domain="example.nl",
            gemeente="Breda",
            score=20,
            confidence=0.65,
            aanbod_url_quality="missing",
            source_origin="seed",
        ),
        SourceCandidate(
            office_name="Example Makelaar Breda",
            website="https://example.nl",
            root_domain="example.nl",
            gemeente="Breda",
            score=80,
            confidence=0.85,
            aanbod_url_quality="valid",
            source_origin="overpass_osm",
            osm_id="123",
        ),
    ]

    deduped = dedupe_candidates(candidates)

    assert len(deduped) == 1
    assert deduped[0].score == 80
    assert deduped[0].source_origin == "overpass_osm+seed"
    assert deduped[0].osm_id == "123"
