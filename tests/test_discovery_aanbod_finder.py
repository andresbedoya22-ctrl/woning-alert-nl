from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.discovery.aanbod_finder import classify_aanbod_url, suggest_common_aanbod_paths


def test_gratis_verkoopadvies_is_not_valid_listing() -> None:
    result = classify_aanbod_url("https://example.nl/gratis-verkoopadvies")

    assert result.status in {"suspect", "rejected"}


def test_aanbod_koopwoningen_is_classified_valid() -> None:
    result = classify_aanbod_url("https://example.nl/aanbod/koopwoningen")

    assert result.status == "valid"


def test_missing_aanbod_url_suggests_common_paths() -> None:
    suggestions = suggest_common_aanbod_paths("https://example.nl")

    assert "https://example.nl/aanbod" in suggestions
    assert "https://example.nl/koopwoningen" in suggestions
