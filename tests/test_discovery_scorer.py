from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.discovery.models import SourceCandidate
from domek_wonen.discovery.scorer import score_candidate


def test_candidate_with_website_and_valid_aanbod_scores_higher() -> None:
    strong = SourceCandidate(
        office_name="Example Makelaar Veldhoven",
        website="https://example.nl",
        root_domain="example.nl",
        gemeente="Veldhoven",
        provincie="Noord-Brabant",
        aanbod_url="https://example.nl/aanbod/koopwoningen/veldhoven",
        aanbod_url_quality="valid",
        confidence=0.85,
    )
    weak = SourceCandidate(
        office_name="Example Makelaar Veldhoven",
        website="https://example.nl",
        root_domain="example.nl",
        gemeente="Veldhoven",
        provincie="Noord-Brabant",
        aanbod_url="",
        aanbod_url_quality="missing",
        confidence=0.65,
    )

    strong_result = score_candidate(strong)
    weak_result = score_candidate(weak)

    assert strong_result.score > weak_result.score
    assert strong_result.status == "valid"


def test_excluded_commercial_page_is_penalized() -> None:
    candidate = SourceCandidate(
        office_name="Example Makelaar",
        website="https://example.nl",
        root_domain="example.nl",
        gemeente="Breda",
        provincie="Noord-Brabant",
        aanbod_url="https://example.nl/gratis-verkoopadvies",
    )

    result = score_candidate(candidate)

    assert result.score < 40
