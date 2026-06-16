from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.properties.property_url_classifier import PropertyUrlClassifier


def test_property_url_classifier_excludes_non_property_paths() -> None:
    classifier = PropertyUrlClassifier()

    urls = [
        "https://example.nl/",
        "https://example.nl/aanbod",
        "https://example.nl/huis-verkopen",
        "https://example.nl/diensten/aankoopmakelaar",
        "https://example.nl/contact",
        "https://example.nl/blog",
    ]

    results = [classifier.classify(url, "example.nl").classification for url in urls]

    assert results == [
        "unknown_non_property",
        "listing_index",
        "service_page",
        "service_page",
        "contact_page",
        "blog_news",
    ]


def test_property_url_classifier_accepts_detail_candidate() -> None:
    result = PropertyUrlClassifier().classify("https://example.nl/aanbod/moleneindplein-163-7189", "example.nl")

    assert result.classification == "property_detail_candidate"
    assert result.is_property_like is True


def test_property_url_classifier_accepts_kin_ogonline_detail_candidate() -> None:
    result = PropertyUrlClassifier().classify(
        "https://www.kinmakelaars.nl/aanbod/wonen/tilburg/roemerhof-16/6a29685e53154f207cdd5c04",
        "kinmakelaars.nl",
    )

    assert result.classification == "property_detail_candidate"
    assert result.is_property_like is True
