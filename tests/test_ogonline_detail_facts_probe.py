from pathlib import Path
import ast
import json
import sys


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.compliance import robots_gate  # noqa: E402
from domek_wonen.parsers.models import ParsedListing  # noqa: E402
from domek_wonen.parsers.source_config import load_parser_source_config  # noqa: E402
from domek_wonen.pilots import ogonline_detail_facts_probe as probe  # noqa: E402
from domek_wonen.pilots import ogonline_detail_property_type_enrichment as enrichment  # noqa: E402


CONFIG_FIXTURE = BASE_DIR / "tests" / "fixtures" / "parsers" / "kin_ogonline_xhr_source_config.json"
MODULE_PATH = BASE_DIR / "scraper" / "src" / "domek_wonen" / "pilots" / "ogonline_detail_facts_probe.py"


def _config():
    return load_parser_source_config(CONFIG_FIXTURE)


def _detail_url(index: int) -> str:
    return f"https://kinmakelaars.nl/aanbod/wonen/breda/facts-{index}/kin-facts-{index:03d}"


def _doc(index: int, **overrides: object) -> dict[str, object]:
    doc: dict[str, object] = {
        "id": f"kin-facts-{index:03d}",
        "url": _detail_url(index),
        "street": "Factsstraat",
        "houseNumber": str(index),
        "postcode": "4811AA",
        "city": "Breda",
        "askingPrice": 410000 + index,
        "isSales": True,
        "status": "available",
        "livingArea": 101,
        "rooms": 5,
        "bedrooms": 3,
    }
    doc.update(overrides)
    return doc


def _payload(*docs: dict[str, object]) -> str:
    return json.dumps({"docs": list(docs)})


def _html() -> str:
    description = "Omschrijving " + ("ruime gezinswoning met licht en goede indeling. " * 8)
    return f"""
    <script>
      window.__DETAIL__ = {{
        "subtype": "Tussenwoning",
        "livingArea": 123,
        "plotArea": 234,
        "rooms": 6,
        "bedrooms": 4,
        "bathrooms": 1,
        "energyLabel": "A++",
        "ownership": "Volle eigendom",
        "serviceCosts": 125,
        "heating": "CV-ketel eigendom",
        "garden": true,
        "balcony": true,
        "storage": true,
        "parking": "eigen oprit",
        "availability": "in overleg",
        "description": "{description}"
      }}
    </script>
    <dl>
      <dt>Perceeloppervlakte</dt><dd>234 m2</dd>
      <dt>Woonoppervlakte</dt><dd>123 m2</dd>
      <dt>Kamers</dt><dd>6 kamers waarvan 4 slaapkamers</dd>
      <dt>Energielabel</dt><dd>A++</dd>
      <dt>Eigendomssituatie</dt><dd>Volle eigendom, eigen grond</dd>
      <dt>VvE bijdrage</dt><dd>125 per maand</dd>
      <dt>Verwarming</dt><dd>CV-ketel eigendom</dd>
      <dt>Buitenruimte</dt><dd>Tuin, balkon en berging</dd>
      <dt>Parkeren</dt><dd>Garage en eigen oprit</dd>
    </dl>
    <span class="badge">Open huis</span>
    <section>Highlights en bijzonderheden beschikbaar. Let op onderhoud aan de schuur.</section>
    """


def test_detects_property_type_from_embedded_state() -> None:
    sample = probe.build_detail_facts_probe_sample(canonical_url=_detail_url(1), html=_html())

    assert "property_type" in sample.fields_present
    assert ("property_type", "Tussenwoning") in sample.field_values_preview
    assert ("property_type", "embedded_state") in sample.extraction_sources


def test_detects_living_area_m2() -> None:
    sample = probe.build_detail_facts_probe_sample(canonical_url=_detail_url(1), html=_html())

    assert ("living_area_m2", "123") in sample.field_values_preview


def test_detects_plot_area_m2() -> None:
    sample = probe.build_detail_facts_probe_sample(canonical_url=_detail_url(1), html=_html())

    assert ("plot_area_m2", "234") in sample.field_values_preview


def test_detects_bedrooms_and_rooms() -> None:
    sample = probe.build_detail_facts_probe_sample(canonical_url=_detail_url(1), html=_html())

    assert "rooms" in sample.fields_present
    assert "bedrooms" in sample.fields_present


def test_detects_energy_label() -> None:
    sample = probe.build_detail_facts_probe_sample(canonical_url=_detail_url(1), html=_html())

    assert ("energy_label", "A++") in sample.field_values_preview


def test_detects_eigendomssituatie() -> None:
    sample = probe.build_detail_facts_probe_sample(canonical_url=_detail_url(1), html=_html())

    assert "eigendomssituatie" in sample.fields_present


def test_detects_vve_monthly_cost() -> None:
    sample = probe.build_detail_facts_probe_sample(canonical_url=_detail_url(1), html=_html())

    assert ("vve_monthly_cost", "125") in sample.field_values_preview
    assert "vve_active" in sample.fields_present


def test_detects_cv_ketel_ownership() -> None:
    sample = probe.build_detail_facts_probe_sample(canonical_url=_detail_url(1), html=_html())

    assert ("cv_ketel_present", "true") in sample.field_values_preview
    assert ("cv_ketel_ownership", "eigendom") in sample.field_values_preview


def test_detects_outdoor_garden_balcony_storage_and_parking_signals() -> None:
    sample = probe.build_detail_facts_probe_sample(canonical_url=_detail_url(1), html=_html())

    assert {"outdoor_space", "garden", "balcony", "storage", "garage", "parking"}.issubset(sample.fields_present)


def test_detects_short_description_source_without_copying_long_description() -> None:
    sample = probe.build_detail_facts_probe_sample(canonical_url=_detail_url(1), html=_html())

    assert ("short_description_source_available", "true") in sample.field_values_preview
    assert "description_length_bucket" in sample.fields_present


def test_description_preview_is_capped_or_absent() -> None:
    sample = probe.build_detail_facts_probe_sample(canonical_url=_detail_url(1), html=_html())

    previews = dict(sample.field_values_preview)
    value = previews.get("short_description_source_available", "")
    assert len(value) <= probe.DESCRIPTION_PREVIEW_LIMIT


def test_max_samples_caps_at_20(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    urls = tuple(_detail_url(index) for index in range(1, 30))

    result = probe.run_ogonline_detail_facts_probe(
        detail_urls=urls,
        source_id="kinmakelaars.nl__breda",
        source_domain="kinmakelaars.nl",
        max_samples=99,
        fetch_html=lambda url: _html(),
    )

    assert result.samples_requested == 20
    assert result.samples_attempted == 20
    assert "max_samples_capped_at_20" in result.warnings


def test_max_api_pages_caps_at_5(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    fetched_pages: list[str] = []

    result = probe.run_kin_ogonline_detail_facts_probe_config(
        _config(),
        fetch_json=lambda url: fetched_pages.append(url) or _payload(_doc(len(fetched_pages))),
        fetch_html=lambda url: _html(),
        max_api_pages=99,
        max_samples=20,
    )

    assert len(fetched_pages) == 5
    assert result.samples_attempted == 5
    assert "max_api_pages_capped_at_5" in result.warnings


def test_robots_false_avoids_api_fetch(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: False)
    fetched = False

    def fetch_json(url: str) -> str:
        nonlocal fetched
        fetched = True
        return _payload(_doc(1))

    result = probe.run_kin_ogonline_detail_facts_probe_config(
        _config(),
        fetch_json=fetch_json,
        fetch_html=lambda url: _html(),
        max_api_pages=1,
        max_samples=1,
    )

    assert fetched is False
    assert result.samples_attempted == 0
    assert "api_blocked_by_robots" in result.warnings


def test_robots_false_avoids_detail_fetch(monkeypatch) -> None:
    def can_fetch(domain: str, path: str) -> bool:
        return domain == "cpl01.ogonline.nl"

    monkeypatch.setattr(robots_gate, "can_fetch", can_fetch)
    fetched_details: list[str] = []

    result = probe.run_kin_ogonline_detail_facts_probe_config(
        _config(),
        fetch_json=lambda url: _payload(_doc(1)),
        fetch_html=lambda url: fetched_details.append(url) or _html(),
        max_api_pages=1,
        max_samples=1,
    )

    assert fetched_details == []
    assert result.samples_attempted == 1
    assert result.samples_failed == 1
    assert "blocked_by_robots" in result.warnings


def test_fetch_exception_does_not_abort_probe(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    def fetch_html(url: str) -> str:
        if "facts-2" in url:
            raise RuntimeError("boom")
        return _html()

    result = probe.run_ogonline_detail_facts_probe(
        detail_urls=(_detail_url(1), _detail_url(2)),
        source_id="kinmakelaars.nl__breda",
        source_domain="kinmakelaars.nl",
        fetch_html=fetch_html,
    )

    assert result.samples_attempted == 2
    assert result.samples_succeeded == 1
    assert result.samples_failed == 1
    assert ("fetch_exception", 1) in result.warning_counts


def test_warning_counts_aggregate_warnings(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    result = probe.run_ogonline_detail_facts_probe(
        detail_urls=(_detail_url(1),),
        source_id="kinmakelaars.nl__breda",
        source_domain="kinmakelaars.nl",
        fetch_html=lambda url: '<script>{"livingArea": 100, "altLivingArea": 120}</script>',
    )

    assert ("missing_fact_source", 1) in result.warning_counts


def test_no_real_network() -> None:
    result = probe.extract_detail_fact_candidates(_html())

    assert result


def test_probe_module_does_not_write_outputs() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    written_methods = {"write_text", "write_bytes", "open"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in written_methods


def test_probe_module_has_no_disallowed_imports() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    imported_roots = {module.split(".")[0] for module in imported_modules}
    assert "requests" not in imported_roots
    assert "httpx" not in imported_roots
    assert "playwright" not in imported_roots
    assert "selenium" not in imported_roots


def test_existing_property_type_enrichment_behavior_is_not_modified(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    listing = ParsedListing(
        source_id="kinmakelaars.nl__breda",
        source_domain="kinmakelaars.nl",
        canonical_url=_detail_url(1),
        address_raw="Factsstraat 1",
        city="Breda",
        asking_price_eur=410000,
        transaction_type="koop",
        status="beschikbaar",
        property_type="",
    )

    result = enrichment.enrich_listings_with_detail_property_type(
        (listing,),
        fetch_html=lambda url: '<script>window.__DETAIL__ = {"subtype":"Appartement"}</script>',
    )

    assert result.enriched_count == 1
    assert result.enriched_listings[0].property_type == "appartement"
