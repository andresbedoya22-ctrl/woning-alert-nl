from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.discovery.models import SourceCandidate
from domek_wonen.discovery.reporter import split_missing_expected_gemeenten


def test_split_missing_expected_gemeenten_separates_zero_candidates_vs_rejected_only() -> None:
    expected = ["Veldhoven", "Breda", "Tilburg"]
    discovered_sources = [
        SourceCandidate(
            office_name="Accepted Breda",
            gemeente="Breda",
            plaats="Breda",
            source_adapter="seed",
            status="valid",
        )
    ]
    rejected_candidates = [
        SourceCandidate(
            office_name="Rejected Veldhoven",
            gemeente="Veldhoven",
            plaats="Veldhoven",
            source_adapter="overpass",
            status="rejected",
        )
    ]

    result = split_missing_expected_gemeenten(expected, discovered_sources, rejected_candidates)

    assert result["missing_expected_with_no_candidates"] == ["Tilburg"]
    assert result["expected_with_candidates_but_no_accepted_sources"] == ["Veldhoven"]
