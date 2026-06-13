from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.properties.models import PropertyCandidate
from domek_wonen.properties.property_dedupe import PropertyDedupe


def test_property_dedupe_eliminates_duplicates_by_property_url() -> None:
    candidates = [
        PropertyCandidate(
            source_id="source-a",
            source_url="https://example.nl/aanbod",
            root_domain="example.nl",
            gemeente="Breda",
            property_url="http://example.nl/woning/kerkstraat-1/",
            title="Kerkstraat 1",
            extraction_confidence=0.55,
        ),
        PropertyCandidate(
            source_id="source-a",
            source_url="https://example.nl/aanbod",
            root_domain="example.nl",
            gemeente="Breda",
            property_url="https://example.nl/woning/kerkstraat-1",
            title="Kerkstraat 1",
            price_raw="€ 395.000 k.k.",
            extraction_confidence=0.82,
        ),
    ]

    deduped = PropertyDedupe().dedupe(candidates)

    assert len(deduped) == 1
    assert deduped[0].price_raw == "€ 395.000 k.k."
