from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.analyze_coverage import (
    aggregate_by_gemeente,
    compute_priority_score,
    recommendation_reason,
)


def test_aggregate_by_gemeente_computes_expected_counts_and_flags() -> None:
    rows = [
        {
            "plaats": "Breda",
            "website": "https://example.com",
            "koopaanbod_url_quality": "valid",
            "needs_review": "false",
        },
        {
            "plaats": "Breda",
            "website": "https://example-2.com",
            "koopaanbod_url_quality": "suspect",
            "needs_review": "true",
        },
        {
            "plaats": "Breda",
            "website": "",
            "koopaanbod_url_quality": "missing",
            "needs_review": "true",
        },
    ]

    result = aggregate_by_gemeente(rows)

    assert result[0]["gemeente"] == "Breda"
    assert result[0]["total_sources"] == "3"
    assert result[0]["with_website"] == "2"
    assert result[0]["with_valid_koopaanbod_url"] == "1"
    assert result[0]["with_suspect_koopaanbod_url"] == "1"
    assert result[0]["missing_koopaanbod_url"] == "1"
    assert result[0]["needs_review_count"] == "2"
    assert result[0]["needs_review_rate"] == "0.6667"
    assert result[0]["valid_aanbod_rate"] == "0.3333"
    assert result[0]["zero_valid_aanbod"] == "false"
    assert result[0]["high_review_rate"] == "true"
    assert result[0]["low_count"] == "false"
    assert result[0]["important_city"] == "true"
    assert result[0]["priority_score"] == "50"


def test_compute_priority_score_applies_all_rules() -> None:
    assert (
        compute_priority_score(
            total_sources=2,
            with_valid_koopaanbod_url=0,
            needs_review_rate=0.50,
            valid_aanbod_rate=0.0,
            important_city=True,
        )
        == 115
    )


def test_recommendation_reason_prioritizes_zero_valid() -> None:
    row = {
        "zero_valid_aanbod": "true",
        "high_review_rate": "true",
        "low_count": "true",
        "important_city": "true",
        "valid_aanbod_rate": "0.0000",
    }

    assert recommendation_reason(row) == "zero_valid_aanbod"
