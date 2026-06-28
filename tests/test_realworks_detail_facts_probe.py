from pathlib import Path
import sys


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.pilots.realworks_detail_facts_probe import (  # noqa: E402
    FIELD_STATUS_AVAILABLE,
    FIELD_STATUS_MISSING,
    FIELD_STATUS_REVIEW,
    build_realworks_detail_facts_probe_sample,
)


def _sample(html: str, *, url: str = "https://example.nl/aanbod/woningaanbod/breda/koop/huis-123-teststraat-1"):
    return build_realworks_detail_facts_probe_sample(canonical_url=url, html=html)


def _field(sample, field: str):
    return {probe.field: probe for probe in sample.fields}[field]


def _facts_html() -> str:
    return """
    <html>
      <head>
        <title>Teststraat 1 | Realworks</title>
        <meta name="description" content="Compacte omschrijving voor lengtebucket." />
      </head>
      <body>
        <dl>
          <dt>Hoofdtype</dt><dd>Eengezinswoning</dd>
          <dt>Vraagprijs</dt><dd>EUR 425.000 k.k.</dd>
          <dt>Status</dt><dd>Beschikbaar</dd>
          <dt>Aantal kamers</dt><dd>5 kamers</dd>
          <dt>Aantal slaapkamers</dt><dd>3 slaapkamers</dd>
          <dt>Badkamers</dt><dd>1 badkamer</dd>
          <dt>Woonoppervlakte</dt><dd>123 m2</dd>
          <dt>Perceeloppervlakte</dt><dd>234 m2</dd>
          <dt>Inhoud</dt><dd>456 m3</dd>
          <dt>Energielabel</dt><dd>C</dd>
          <dt>Bouwjaar</dt><dd>1998</dd>
          <dt>Cv-ketel</dt><dd>Remeha HR combiketel</dd>
          <dt>Isolatie</dt><dd>Dubbel glas</dd>
          <dt>Tuintypes</dt><dd>Achtertuin</dd>
          <dt>Parkeertypes</dt><dd>Openbaar parkeren</dd>
          <dt>Garagetypes</dt><dd>Geen garage</dd>
          <dt>VvE bijdrage</dt><dd>Niet van toepassing</dd>
          <dt>Eigendomssituatie</dt><dd>Volle eigendom</dd>
        </dl>
      </body>
    </html>
    """


def test_extracts_living_area_plot_area_and_volume() -> None:
    sample = _sample(_facts_html())

    assert _field(sample, "living_area_m2").normalized_value == 123
    assert _field(sample, "plot_area_m2").normalized_value == 234
    assert _field(sample, "volume_m3").normalized_value == 456


def test_extracts_rooms_but_not_bedrooms_from_rooms() -> None:
    sample = _sample("<dl><dt>Aantal kamers</dt><dd>5 kamers</dd></dl>")

    assert _field(sample, "rooms").normalized_value == 5
    assert _field(sample, "rooms").status == FIELD_STATUS_AVAILABLE
    assert _field(sample, "bedrooms").status == FIELD_STATUS_MISSING


def test_extracts_bedrooms_from_strong_bedroom_label() -> None:
    sample = _sample("<dl><dt>Aantal slaapkamers</dt><dd>3 slaapkamers</dd></dl>")

    assert _field(sample, "bedrooms").normalized_value == 3
    assert _field(sample, "bedrooms").status == FIELD_STATUS_AVAILABLE


def test_extracts_energy_label_c_and_does_not_extract_e_from_label_word() -> None:
    sample = _sample("<dl><dt>Energielabel</dt><dd>Energielabel C</dd></dl>")
    missing = _sample("<dl><dt>Energielabel</dt><dd>Energielabel</dd></dl>")

    assert _field(sample, "energy_label").normalized_value == "C"
    assert _field(sample, "energy_label").status == FIELD_STATUS_AVAILABLE
    assert _field(missing, "energy_label").status == FIELD_STATUS_REVIEW
    assert _field(missing, "energy_label").normalized_value is None


def test_extracts_bouwjaar_and_cv_ketel_conservatively() -> None:
    sample = _sample("<dl><dt>Bouwjaar</dt><dd>1998</dd><dt>Cv-ketel</dt><dd>Remeha HR combiketel</dd></dl>")

    assert _field(sample, "bouwjaar").normalized_value == 1998
    assert _field(sample, "heating").normalized_value == "remeha hr combiketel"


def test_does_not_produce_false_erfpacht() -> None:
    sample = _sample("<dl><dt>Erfpacht</dt><dd>Geen erfpacht</dd></dl>")

    assert _field(sample, "ownership_or_erfpacht").status == FIELD_STATUS_MISSING
    assert _field(sample, "ownership_or_erfpacht").normalized_value is None


def test_description_only_records_length_bucket() -> None:
    long_description = "Ruime woning. " * 80
    sample = _sample(f"<meta name='description' content='{long_description}'><p>{long_description}</p>")
    field = _field(sample, "description_length_bucket")
    serialized = repr(sample).casefold()

    assert field.normalized_value == "long"
    assert "ruime woning. ruime woning. ruime woning." not in serialized


def test_missing_and_review_are_explicit() -> None:
    sample = _sample("<dl><dt>Woonoppervlakte</dt><dd>nader te bepalen</dd></dl>")

    assert _field(sample, "living_area_m2").status == FIELD_STATUS_REVIEW
    assert _field(sample, "bedrooms").status == FIELD_STATUS_MISSING
    assert "review_fact_source" in sample.warnings
    assert "missing_fact_source" in sample.warnings


def test_probe_does_not_depend_on_oldenkotte_domain() -> None:
    sample = _sample(
        _facts_html(),
        url="https://gewoonmakelaars.nl/aanbod/woningaanbod/breda/koop/huis-123-teststraat-1",
    )

    assert sample.canonical_url.startswith("https://gewoonmakelaars.nl/")
    assert _field(sample, "living_area_m2").normalized_value == 123
