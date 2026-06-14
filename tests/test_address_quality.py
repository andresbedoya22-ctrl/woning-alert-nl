from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.properties.address_quality import classify_address_quality, derive_address_from_slug


def test_address_quality_valid_vier_heultjes() -> None:
    assert classify_address_quality("Vier Heultjes 99", "https://example.nl/woningen/vier-heultjes-99-sprang-capelle") == "valid"


def test_address_quality_valid_christoffel_wuststraat() -> None:
    assert (
        classify_address_quality(
            "Christoffel Wüststraat 34",
            "https://example.nl/woningen/christoffel-wuststraat-34-rosmalen",
        )
        == "valid"
    )


def test_address_quality_invalid_long_menu_text() -> None:
    value = (
        "Diensten Verkoop Aankoop Taxatie Energielabel Snel naar Aanbod "
        "Aankopen Verkopen Taxeren Contact Over ons Veelgestelde vragen 123"
    )
    assert classify_address_quality(value, "https://example.nl/woningen/example-12-breda") == "invalid"


def test_address_quality_invalid_kk_menu_text() -> None:
    assert classify_address_quality("k.k. Snel naar Aanbod Aankopen Verkopen 12", "https://example.nl/woningen/example-12-breda") == "invalid"


def test_derive_address_from_slug_returns_legible_address() -> None:
    address_raw, city_raw = derive_address_from_slug("https://example.nl/woningen/vier-heultjes-99-sprang-capelle")

    assert address_raw == "Vier Heultjes 99"
    assert city_raw == "Sprang-Capelle"
