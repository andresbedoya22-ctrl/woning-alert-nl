from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.properties.property_status_classifier import PropertyStatusClassifier


def test_status_classifier_maps_expected_statuses() -> None:
    classifier = PropertyStatusClassifier()

    assert classifier.classify("Onder bod") == "onder_bod"
    assert classifier.classify("Verkocht onder voorbehoud") == "verkocht_ov"
    assert classifier.classify("Verkocht") == "verkocht"
    assert classifier.classify("€ 395.000 k.k.", "Appartement te koop") == "beschikbaar"
