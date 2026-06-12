from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.import_sources import (
    compute_confidence,
    compute_needs_review,
    extract_root_domain,
    is_valid_koopaanbod_url,
    normalize_url,
    normalize_rows,
)


def test_normalize_url_adds_https_if_missing() -> None:
    assert normalize_url("example.com") == "https://example.com"


def test_normalize_url_removes_trailing_slash() -> None:
    assert normalize_url("https://example.com/") == "https://example.com"


def test_extract_root_domain_handles_subdomains() -> None:
    assert extract_root_domain("search.office.example.co.uk") == "example.co.uk"


def test_needs_review_is_true_when_koopaanbod_url_missing() -> None:
    assert compute_needs_review("https://example.com", "example.com", "") is True


def test_confidence_rules_match_spec() -> None:
    assert compute_confidence("https://example.com", "https://example.com/koop") == 0.85
    assert compute_confidence("https://example.com", "") == 0.65
    assert compute_confidence("", "") == 0.40


def test_is_valid_koopaanbod_url_rejects_gratis_verkoopadvies() -> None:
    assert is_valid_koopaanbod_url("https://example.com/gratis-verkoopadvies") == (
        False,
        "contains excluded token 'gratis-verkoopadvies'",
    )


def test_is_valid_koopaanbod_url_rejects_verkoopadvies() -> None:
    assert is_valid_koopaanbod_url("https://example.com/verkoopadvies") == (
        False,
        "contains excluded token 'verkoopadvies'",
    )


def test_is_valid_koopaanbod_url_rejects_contact() -> None:
    assert is_valid_koopaanbod_url("https://example.com/contact") == (
        False,
        "contains excluded token 'contact'",
    )


def test_is_valid_koopaanbod_url_accepts_aanbod_koopwoningen() -> None:
    assert is_valid_koopaanbod_url("https://example.com/aanbod/koopwoningen") == (True, "valid")


def test_is_valid_koopaanbod_url_accepts_woningaanbod_koop_path() -> None:
    assert is_valid_koopaanbod_url("https://example.com/woningaanbod/brabant/koop/appartementen") == (
        True,
        "valid",
    )


def test_suspect_koopaanbod_url_forces_needs_review() -> None:
    rows, _stats = normalize_rows(
        [
            {
                "naam": "Example Makelaars",
                "plaats": "Breda",
                "website": "https://example.com",
                "koopaanbod_url": "https://example.com/contact",
                "notas": "",
            }
        ]
    )
    assert rows[0]["koopaanbod_url_quality"] == "suspect"
    assert rows[0]["needs_review"] == "true"


def test_suspect_koopaanbod_url_caps_confidence_at_065() -> None:
    rows, _stats = normalize_rows(
        [
            {
                "naam": "Example Makelaars",
                "plaats": "Breda",
                "website": "https://example.com",
                "koopaanbod_url": "https://example.com/contact",
                "notas": "",
            }
        ]
    )
    assert rows[0]["confidence"] == "0.65"
