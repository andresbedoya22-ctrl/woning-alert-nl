from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
import sys


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.facts import (  # noqa: E402
    PropertyFactsRecord,
    extract_realworks_property_facts_from_html,
    record_to_dict,
)


NOW = datetime(2026, 6, 28, tzinfo=UTC)


def _kenmerk(label: str, value: str) -> str:
    return f"""
    <span class="kenmerk">
      <span class="kenmerkName">{label}</span>
      <span class="kenmerkValue">{value}</span>
    </span>
    """


def _html(*pairs: tuple[str, str], description: str = "Compacte omschrijving.") -> str:
    facts = "\n".join(_kenmerk(label, value) for label, value in pairs)
    return f"""
    <html>
      <head><meta name="description" content="{description}"></head>
      <body>{facts}</body>
    </html>
    """


def _extract(html: str, **fallbacks: object):
    return extract_realworks_property_facts_from_html(
        html=html,
        source_id="example.nl__test",
        source_domain="example.nl",
        canonical_url="https://example.nl/aanbod/woningaanbod/breda/koop/huis-123-teststraat-1",
        address_raw="Teststraat 1",
        city="Breda",
        status="beschikbaar",
        fetched_at=NOW,
        listing_fallbacks=fallbacks,
    )


def _facts(result) -> dict[str, object]:
    return {fact.field: fact for fact in result.record.facts}


def test_extracts_woonoppervlakte_to_living_area() -> None:
    facts = _facts(_extract(_html(("Woonoppervlakte", "123 m2"))))

    assert facts["living_area_m2"].normalized_value == 123
    assert facts["living_area_m2"].status == "usable"


def test_extracts_perceeloppervlakte_to_plot_area() -> None:
    facts = _facts(_extract(_html(("Perceeloppervlakte", "234 m2"))))

    assert facts["plot_area_m2"].normalized_value == 234


def test_extracts_inhoud_to_volume() -> None:
    facts = _facts(_extract(_html(("Inhoud", "456 m3"))))

    assert facts["volume_m3"].normalized_value == 456


def test_extracts_aantal_kamers_to_rooms() -> None:
    facts = _facts(_extract(_html(("Aantal kamers", "5 kamers"))))

    assert facts["rooms"].normalized_value == 5


def test_does_not_infer_bedrooms_from_rooms() -> None:
    facts = _facts(_extract(_html(("Aantal kamers", "5 kamers"))))

    assert facts["bedrooms"].status == "missing"
    assert facts["bedrooms"].normalized_value is None


def test_extracts_aantal_slaapkamers_to_bedrooms() -> None:
    facts = _facts(_extract(_html(("Aantal slaapkamers", "3 slaapkamers"))))

    assert facts["bedrooms"].normalized_value == 3


def test_extracts_aantal_badkamers_to_bathrooms() -> None:
    facts = _facts(_extract(_html(("Aantal badkamers", "1 badkamer"))))

    assert facts["bathrooms"].normalized_value == 1


def test_extracts_explicit_energieklasse_b() -> None:
    facts = _facts(_extract(_html(("Energieklasse", "B"))))

    assert facts["energy_label"].normalized_value == "B"
    assert facts["energy_label"].status == "usable"


def test_does_not_extract_energy_label_from_label_text_alone() -> None:
    facts = _facts(_extract(_html(("Energieklasse", "Energieklasse"))))

    assert facts["energy_label"].normalized_value is None
    assert facts["energy_label"].status == "review"


def test_non_explicit_energy_label_becomes_review() -> None:
    facts = _facts(_extract(_html(("Energieklasse", "Energielabel aanwezig"))))

    assert facts["energy_label"].status == "review"
    assert "energy_label_not_explicit" in facts["energy_label"].warnings


def test_niet_aanwezig_energy_label_is_review_not_usable() -> None:
    facts = _facts(_extract(_html(("Energieklasse", "Niet aanwezig"))))

    assert facts["energy_label"].normalized_value is None
    assert facts["energy_label"].value == "Niet aanwezig"
    assert facts["energy_label"].status == "review"
    assert "energy_label_not_explicit" in facts["energy_label"].warnings


def test_extracts_bouwjaar() -> None:
    facts = _facts(_extract(_html(("Bouwjaar", "1998"))))

    assert facts["bouwjaar"].normalized_value == 1998


def test_extracts_vraagprijs() -> None:
    facts = _facts(_extract(_html(("Vraagprijs", "EUR 425.000 k.k."))))

    assert facts["asking_price"].normalized_value == 425000


def test_extracts_verwarming() -> None:
    facts = _facts(_extract(_html(("Verwarming", "CV-ketel"))))

    assert facts["heating_type"].normalized_value == "cv_ketel"


def test_extracts_geen_tuin_as_usable_explicit_value() -> None:
    facts = _facts(_extract(_html(("Tuin", "Geen tuin"))))

    assert facts["garden"].normalized_value == "geen_tuin"
    assert facts["garden"].status == "usable"


def test_does_not_create_false_erfpacht_from_volle_eigendom() -> None:
    facts = _facts(_extract(_html(("Eigendomssituatie", "Volle eigendom"))))

    assert facts["eigendomssituatie"].normalized_value == "volle_eigendom"
    assert facts["eigendomssituatie"].normalized_value != "erfpacht"


def test_extracts_explicit_erfpacht_if_present() -> None:
    facts = _facts(_extract(_html(("Eigendomssituatie", "Erfpacht"))))

    assert facts["eigendomssituatie"].normalized_value == "erfpacht"


def test_marks_overigog_property_type_as_review_unsupported() -> None:
    facts = _facts(_extract(_html(("Soort object", "OverigOG"))))

    assert facts["property_type"].status == "review"
    assert facts["property_type"].normalized_value == "unknown"
    assert "unsupported_property_type_overigog" in facts["property_type"].warnings
    assert "non_residential_property_type" in facts["property_type"].warnings


def test_marks_garage_property_type_as_non_residential_warning() -> None:
    facts = _facts(_extract(_html(("Soort object", "Garage"))))

    assert facts["property_type"].normalized_value == "garage"
    assert facts["property_type"].status == "review"
    assert "non_residential_property_type" in facts["property_type"].warnings


def test_extracts_vve_labels() -> None:
    facts = _facts(_extract(_html(("VvE", "Ja"), ("Bijdrage VvE", "EUR 125 per maand"))))

    assert facts["vve_active"].normalized_value is True
    assert facts["vve_active"].status == "usable"
    assert facts["vve_monthly_cost"].normalized_value == 125


def test_keeps_descriptions_as_length_bucket_only() -> None:
    long_description = "Ruime woning met licht en tuin. " * 80
    result = _extract(_html(("Woonoppervlakte", "123 m2"), description=long_description))
    facts = _facts(result)
    serialized = json.dumps(record_to_dict(result.record)).casefold()

    assert facts["description_length_bucket"].normalized_value == "long"
    assert "ruime woning met licht en tuin" not in serialized
    assert "description_not_stored" in result.warnings


def test_uses_listing_card_fallback_for_price_and_status_only_when_detail_missing() -> None:
    facts = _facts(_extract(_html(("Woonoppervlakte", "123 m2")), asking_price=399000, status="beschikbaar"))

    assert facts["asking_price"].normalized_value == 399000
    assert facts["asking_price"].source == "listing_fallback"
    assert facts["availability_date"].normalized_value == "beschikbaar"
    assert facts["availability_date"].source == "listing_fallback"


def test_detail_price_wins_over_listing_card_fallback() -> None:
    facts = _facts(_extract(_html(("Vraagprijs", "EUR 425.000 k.k.")), asking_price=399000, status="beschikbaar"))

    assert facts["asking_price"].normalized_value == 425000
    assert facts["asking_price"].source == "realworks_kenmerk"


def test_does_not_depend_on_oldenkotte_domain() -> None:
    result = extract_realworks_property_facts_from_html(
        html=_html(("Woonoppervlakte", "123 m2")),
        source_id="gewoonmakelaars.nl__breda",
        source_domain="gewoonmakelaars.nl",
        canonical_url="https://gewoonmakelaars.nl/aanbod/woningaanbod/breda/koop/huis-123-teststraat-1",
        address_raw="Teststraat 1",
        city="Breda",
        status="beschikbaar",
        fetched_at=NOW,
    )

    assert _facts(result)["living_area_m2"].normalized_value == 123
    assert result.record.source_domain == "gewoonmakelaars.nl"


def test_builds_stable_property_facts_record_with_source_metadata_and_warnings() -> None:
    result = _extract(_html(("Garage", "Mogelijk garagebox"), ("C.V.-ketel", "Remeha HR")))

    assert isinstance(result.record, PropertyFactsRecord)
    assert result.record.source_id == "example.nl__test"
    assert result.record.address_raw == "Teststraat 1"
    assert all(len(fact.evidence_preview) <= 160 for fact in result.record.facts)
    assert len(_facts(result)["garage"].evidence_preview) <= 120
    assert _facts(result)["garage"].status == "review"
    assert "garage_ambiguous" in result.warnings
    assert "cv_ketel_ownership_not_clear" in result.warnings
