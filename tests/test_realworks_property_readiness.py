from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path
import sys


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.compliance import robots_gate  # noqa: E402
from domek_wonen.facts import build_property_fact_value, build_property_facts_record  # noqa: E402
from domek_wonen.parsers.models import ParsedListing  # noqa: E402
from domek_wonen.pilots.realworks_property_readiness import (  # noqa: E402
    build_realworks_property_readiness_row,
    classify_realworks_export_readiness,
    run_realworks_property_readiness,
)


MODULE_PATH = BASE_DIR / "scraper" / "src" / "domek_wonen" / "pilots" / "realworks_property_readiness.py"
NOW = datetime(2026, 6, 28, tzinfo=UTC)


def _listing(**overrides: object) -> ParsedListing:
    listing = ParsedListing(
        source_id="example.nl__breda",
        source_domain="example.nl",
        canonical_url="https://example.nl/aanbod/woningaanbod/breda/koop/huis-123-teststraat-1",
        address_raw="Teststraat 1",
        street="Teststraat",
        house_number="1",
        postcode="4811AA",
        city="Breda",
        asking_price_eur=425000,
        transaction_type="koop",
        status="beschikbaar",
        living_area_m2=123,
        rooms_count=5,
        bedrooms_count=3,
        property_type="woonhuis",
        confidence_score=0.95,
    )
    values = {field: getattr(listing, field) for field in listing.__dataclass_fields__}
    values.update(overrides)
    return ParsedListing(**values)


def _fact(field: str, value: object, *, normalized_value: object | None = None, status: str = "usable", warnings=()):
    return build_property_fact_value(
        field=field,
        value=value,
        normalized_value=value if normalized_value is None else normalized_value,
        source="realworks_kenmerk",
        confidence=0.90,
        status=status,
        evidence_preview=str(value or ""),
        warnings=warnings,
    )


def _record(*facts, url: str = "https://example.nl/aanbod/woningaanbod/breda/koop/huis-123-teststraat-1", warnings=()):
    return build_property_facts_record(
        source_id="example.nl__breda",
        source_domain="example.nl",
        canonical_url=url,
        address_raw="Teststraat 1",
        city="Breda",
        status="beschikbaar",
        fetched_at="2026-06-28T00:00:00Z",
        expires_at="2026-07-12T00:00:00Z",
        facts=facts,
        warnings=warnings,
    )


def _full_record(**overrides: object):
    values = {
        "asking_price": _fact("asking_price", 425000),
        "property_type": _fact("property_type", "Woonhuis", normalized_value="woonhuis"),
        "living_area_m2": _fact("living_area_m2", 123),
        "bedrooms": _fact("bedrooms", 3),
        "bathrooms": _fact("bathrooms", 1),
        "energy_label": _fact("energy_label", "A"),
        "bouwjaar": _fact("bouwjaar", 1998),
        "heating_type": _fact("heating_type", "CV-ketel", normalized_value="cv_ketel"),
        "parking": _fact("parking", "Openbaar parkeren"),
        "eigendomssituatie": _fact("eigendomssituatie", "Volle eigendom", normalized_value="volle_eigendom"),
        "description_length_bucket": _fact("description_length_bucket", "medium"),
    }
    values.update(overrides)
    return _record(*values.values())


def _apartment_record(**overrides: object):
    values = {
        "asking_price": _fact("asking_price", 425000),
        "property_type": _fact("property_type", "Appartement", normalized_value="appartement"),
        "living_area_m2": _fact("living_area_m2", 83),
        "bedrooms": _fact("bedrooms", 2),
        "bathrooms": _fact("bathrooms", 1),
        "energy_label": _fact("energy_label", "A"),
        "bouwjaar": _fact("bouwjaar", 1998),
        "heating_type": _fact("heating_type", "CV-ketel", normalized_value="cv_ketel"),
        "parking": _fact("parking", "Openbaar parkeren"),
        "eigendomssituatie": _fact("eigendomssituatie", "Volle eigendom", normalized_value="volle_eigendom"),
        "description_length_bucket": _fact("description_length_bucket", "medium"),
    }
    values.update(overrides)
    return _record(*values.values())


def _detail_html(*, energy: str = "A", bedrooms: str = "3 slaapkamers", property_type: str = "Woonhuis") -> str:
    return f"""
    <html>
      <head><meta name="description" content="Compacte omschrijving voor bucket."></head>
      <body>
        <span class="kenmerk"><span class="kenmerkName">Soort object</span><span class="kenmerkValue">{property_type}</span></span>
        <span class="kenmerk"><span class="kenmerkName">Vraagprijs</span><span class="kenmerkValue">EUR 425.000 k.k.</span></span>
        <span class="kenmerk"><span class="kenmerkName">Status</span><span class="kenmerkValue">Beschikbaar</span></span>
        <span class="kenmerk"><span class="kenmerkName">Woonoppervlakte</span><span class="kenmerkValue">123 m2</span></span>
        <span class="kenmerk"><span class="kenmerkName">Perceeloppervlakte</span><span class="kenmerkValue">234 m2</span></span>
        <span class="kenmerk"><span class="kenmerkName">Aantal kamers</span><span class="kenmerkValue">5 kamers</span></span>
        <span class="kenmerk"><span class="kenmerkName">Aantal slaapkamers</span><span class="kenmerkValue">{bedrooms}</span></span>
        <span class="kenmerk"><span class="kenmerkName">Aantal badkamers</span><span class="kenmerkValue">1 badkamer</span></span>
        <span class="kenmerk"><span class="kenmerkName">Inhoud</span><span class="kenmerkValue">456 m3</span></span>
        <span class="kenmerk"><span class="kenmerkName">Energieklasse</span><span class="kenmerkValue">{energy}</span></span>
        <span class="kenmerk"><span class="kenmerkName">Bouwjaar</span><span class="kenmerkValue">1998</span></span>
        <span class="kenmerk"><span class="kenmerkName">Verwarming</span><span class="kenmerkValue">CV-ketel</span></span>
        <span class="kenmerk"><span class="kenmerkName">Tuin</span><span class="kenmerkValue">Achtertuin</span></span>
        <span class="kenmerk"><span class="kenmerkName">Parkeerfaciliteiten</span><span class="kenmerkValue">Openbaar parkeren</span></span>
        <span class="kenmerk"><span class="kenmerkName">Eigendomssituatie</span><span class="kenmerkValue">Volle eigendom</span></span>
      </body>
    </html>
    """


def _listing_html() -> str:
    return """
    <html><body>
      <li class="aanbodEntry">
        <a href="/aanbod/woningaanbod/breda/koop/huis-123-teststraat-1">
          <span class="street-address">Teststraat 1</span>
          <span class="locality">Breda</span>
          <span class="price">EUR 425.000 k.k.</span>
          <span class="objectstatusbanner">Beschikbaar</span>
          <span>Woonhuis 123 m2 5 kamers Te koop</span>
        </a>
      </li>
    </body></html>
    """


def test_builds_row_from_qa_clean_listing_and_usable_facts() -> None:
    row = build_realworks_property_readiness_row(_listing(), _full_record())

    assert row.source_id == "example.nl__breda"
    assert row.property_link == row.canonical_url
    assert row.asking_price == 425000
    assert row.client_summary.headline


def test_client_ready_when_critical_fields_are_usable() -> None:
    row = build_realworks_property_readiness_row(_listing(), _full_record())

    assert row.quality_status == "client_ready"
    assert classify_realworks_export_readiness(row) == "export_ready"


def test_advisor_review_when_energy_label_is_review() -> None:
    record = _full_record(energy_label=_fact("energy_label", "Niet aanwezig", normalized_value=None, status="review", warnings=("energy_label_not_explicit",)))
    row = build_realworks_property_readiness_row(_listing(), record)

    assert row.quality_status == "advisor_review"
    assert "energy_label" in row.review_fields
    assert row.energy_label is None
    assert row.energy_label_raw == "Niet aanwezig"
    assert row.energy_label_status == "review"


def test_advisor_review_when_bedrooms_are_missing() -> None:
    record = _full_record(bedrooms=_fact("bedrooms", None, normalized_value=None, status="missing"))
    row = build_realworks_property_readiness_row(_listing(), record)

    assert row.quality_status == "advisor_review"
    assert "bedrooms" in row.missing_key_fields


def test_advisor_review_when_postcode_is_missing() -> None:
    row = build_realworks_property_readiness_row(_listing(postcode=""), _full_record())

    assert row.quality_status == "advisor_review"
    assert "postcode" in row.missing_key_fields
    assert "missing_postcode" in row.warnings
    assert row.postcode_status == "missing"
    assert row.postcode_source == "missing_not_extracted"


def test_usable_postcode_removes_missing_postcode_warning() -> None:
    row = build_realworks_property_readiness_row(_listing(postcode="5044 SN"), _full_record())

    assert row.postcode == "5044 SN"
    assert row.postcode_status == "usable"
    assert "postcode" not in row.missing_key_fields
    assert "missing_postcode" not in row.warnings


def test_blocked_when_canonical_url_is_missing() -> None:
    row = build_realworks_property_readiness_row(_listing(canonical_url=""), _full_record())

    assert row.quality_status == "blocked"
    assert row.export_readiness == "export_blocked"


def test_blocked_when_address_is_missing() -> None:
    row = build_realworks_property_readiness_row(_listing(address_raw="", street=""), _full_record())

    assert row.quality_status == "blocked"


def test_blocked_when_price_is_missing() -> None:
    record = _full_record(asking_price=_fact("asking_price", None, normalized_value=None, status="missing"))
    row = build_realworks_property_readiness_row(_listing(), record)

    assert row.quality_status == "blocked"


def test_overigog_is_not_client_ready() -> None:
    record = _full_record(
        property_type=_fact(
            "property_type",
            "OverigOG",
            normalized_value="unknown",
            status="review",
            warnings=("unsupported_property_type_overigog",),
        )
    )
    row = build_realworks_property_readiness_row(_listing(), record)

    assert row.residential_classification == "non_residential_blocked"
    assert row.quality_status == "blocked"
    assert row.export_readiness == "export_blocked"
    assert "non_residential_property_type" in row.warnings


def test_garage_property_type_is_blocked_as_non_residential() -> None:
    record = _full_record(property_type=_fact("property_type", "Garage", normalized_value="garage", status="review", warnings=("non_residential_property_type",)))
    row = build_realworks_property_readiness_row(_listing(property_type="garage"), record)

    assert row.residential_classification == "non_residential_blocked"
    assert row.quality_status == "blocked"
    assert row.export_readiness == "export_blocked"
    assert row.active_inventory_eligible is False
    assert row.db_persistence_action == "store_excluded_non_residential"


def test_apartment_without_vve_requires_review() -> None:
    row = build_realworks_property_readiness_row(_listing(property_type="appartement"), _apartment_record())

    assert row.vve_status == "missing"
    assert row.vve_missing_reason == "missing_vve_for_apartment"
    assert "missing_vve_for_apartment" in row.warnings
    assert "vve_active" in row.missing_key_fields
    assert row.quality_status == "advisor_review"


def test_woonhuis_without_vve_does_not_warn() -> None:
    row = build_realworks_property_readiness_row(_listing(), _full_record())

    assert row.vve_status == "not_applicable"
    assert "missing_vve_for_apartment" not in row.warnings


def test_missing_lat_lon_reported_as_gap_not_invented() -> None:
    row = build_realworks_property_readiness_row(_listing(), _full_record())

    assert row.location_readiness.latitude is None
    assert row.location_readiness.longitude is None
    assert "missing_coordinates" in row.warnings
    assert row.quality_status == "client_ready"


def test_client_summary_does_not_invent_missing_facts() -> None:
    record = _full_record(energy_label=_fact("energy_label", None, normalized_value=None, status="missing"))
    row = build_realworks_property_readiness_row(_listing(), record)

    assert "energy_label" in row.client_summary.missing_key_fields
    assert "label" not in row.client_summary.energy_line.casefold()


def test_long_descriptions_are_not_included() -> None:
    row = build_realworks_property_readiness_row(_listing(), _full_record())

    assert "Compacte omschrijving" not in repr(row)
    assert "<html" not in repr(row).casefold()


def test_warnings_are_propagated() -> None:
    record = _record(
        _fact("asking_price", 425000),
        _fact("property_type", "Woonhuis", normalized_value="woonhuis"),
        _fact("living_area_m2", 123),
        _fact("bedrooms", 3),
        _fact("bathrooms", 1),
        _fact("energy_label", "A"),
        _fact("bouwjaar", 1998),
        _fact("heating_type", "CV-ketel", normalized_value="cv_ketel"),
        _fact("parking", "Openbaar parkeren"),
        _fact("eigendomssituatie", "Volle eigendom", normalized_value="volle_eigendom"),
        warnings=("description_not_stored",),
    )
    row = build_realworks_property_readiness_row(_listing(), record)

    assert "description_not_stored" in row.warnings


def test_runner_has_no_domain_specific_behavior(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    result = run_realworks_property_readiness(
        source_id="another.nl__breda",
        source_domain="another.nl",
        listing_url="https://another.nl/aanbod/woningaanbod/koop",
        fetch_html=lambda url: _listing_html().replace("example.nl", "another.nl") if url.endswith("/koop") else _detail_html(),
        now=NOW,
    )

    assert result.source_domain == "another.nl"
    assert result.readiness_rows_built == 1


def test_export_readiness_maps_correctly() -> None:
    ready = build_realworks_property_readiness_row(_listing(), _full_record())
    review = build_realworks_property_readiness_row(_listing(postcode=""), _full_record())
    blocked = build_realworks_property_readiness_row(_listing(canonical_url=""), _full_record())

    assert ready.export_readiness == "export_ready"
    assert review.export_readiness == "export_review"
    assert blocked.export_readiness == "export_blocked"


def test_verkocht_is_history_only_not_active_inventory() -> None:
    row = build_realworks_property_readiness_row(_listing(status="verkocht"), _full_record())

    assert row.status_bucket == "inactive_sold"
    assert row.active_inventory_eligible is False
    assert row.db_persistence_action == "store_status_history"


def test_verkocht_onder_voorbehoud_is_history_only_not_active_inventory() -> None:
    row = build_realworks_property_readiness_row(_listing(status="verkocht onder voorbehoud"), _full_record())

    assert row.status_bucket == "inactive_under_contract"
    assert row.active_inventory_eligible is False
    assert row.db_persistence_action == "store_status_history"


def test_beschikbaar_residential_ready_can_be_active_inventory_eligible() -> None:
    row = build_realworks_property_readiness_row(_listing(status="beschikbaar"), _full_record())

    assert row.quality_status == "client_ready"
    assert row.status_bucket == "active_available"
    assert row.active_inventory_eligible is True
    assert row.db_persistence_action == "store_active_candidate"


def test_runner_aggregates_counts_without_live_network(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    result = run_realworks_property_readiness(
        source_id="example.nl__breda",
        source_domain="example.nl",
        listing_url="https://example.nl/aanbod/woningaanbod/koop",
        fetch_html=lambda url: _listing_html() if url.endswith("/koop") else _detail_html(energy="Niet aanwezig"),
        now=NOW,
    )

    assert result.listing_parser_total == 1
    assert result.listing_qa_clean == 1
    assert result.detail_attempted == 1
    assert result.detail_succeeded == 1
    assert result.facts_records_built == 1
    assert result.readiness_rows_built == 1
    assert ("advisor_review", 1) in result.quality_status_counts
    assert ("export_review", 1) in result.export_readiness_counts
    assert ("energy_label", 0, 1, 0) in result.field_completion_counts
    assert ("energy_label", 1) in result.review_fields_counts
    assert ("energy_label_not_explicit", 1) in result.warning_counts
    assert result.problem_rows_compact


def test_no_disallowed_imports() -> None:
    disallowed = {"requests", "httpx", "playwright", "selenium"}
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    assert disallowed.isdisjoint({module.split(".")[0] for module in imported_modules})
