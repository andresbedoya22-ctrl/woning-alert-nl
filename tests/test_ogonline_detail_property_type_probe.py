from pathlib import Path
import ast
import json
import sys


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.compliance import robots_gate  # noqa: E402
from domek_wonen.parsers.models import ParsedListing  # noqa: E402
from domek_wonen.parsers.source_config import (  # noqa: E402
    PaginatedAPIConfig,
    ParserSourceConfig,
)
from domek_wonen.pilots import ogonline_detail_property_type_probe as probe  # noqa: E402


MODULE_PATH = BASE_DIR / "scraper" / "src" / "domek_wonen" / "pilots" / "ogonline_detail_property_type_probe.py"


def _listing(
    index: int,
    *,
    status: str = "beschikbaar",
    property_type: str = "",
    price: int | None = 400000,
    city: str = "Breda",
) -> ParsedListing:
    return ParsedListing(
        source_id="kinmakelaars.nl__breda",
        source_domain="kinmakelaars.nl",
        canonical_url=f"https://kinmakelaars.nl/aanbod/wonen/breda/example-{index}/id-{index}",
        address_raw=f"Example Street {index}",
        city=city,
        asking_price_eur=price,
        transaction_type="koop",
        status=status,
        property_type=property_type,
    )


def _config() -> ParserSourceConfig:
    return ParserSourceConfig(
        source_id="kinmakelaars.nl__breda",
        source_domain="kinmakelaars.nl",
        listing_url="https://kinmakelaars.nl/aanbod/wonen/te-koop",
        parser_family="ogonline_xhr",
        delivery_mode="ogonline_xhr",
        api=PaginatedAPIConfig(
            api_base_url="https://cpl01.ogonline.nl/api/listings",
            max_pages=2,
            static_query_params={"account": "kin"},
        ),
    )


def test_extracts_woonhuis_from_json_ld_breadcrumb_and_kenmerken() -> None:
    html = """
    <script type="application/ld+json">
      {"@type":"BreadcrumbList","itemListElement":[{"name":"Woonhuis"}]}
    </script>
    <nav class="breadcrumb">Home / Aanbod / Woonhuis</nav>
    <dl><dt>Woningtype</dt><dd>Woonhuis</dd></dl>
    """

    result = probe.extract_detail_candidates(html)

    assert result.property_type_candidates == ("Woonhuis",)
    assert any(signal.startswith("json_ld:property_type:Woonhuis") for signal in result.evidence_signals)
    assert any(signal.startswith("breadcrumb:property_type:Woonhuis") for signal in result.evidence_signals)
    assert any(signal.startswith("label_context:property_type:Woonhuis") for signal in result.evidence_signals)


def test_extracts_appartement_from_detail_text() -> None:
    html = "<main><h1>Appartement in Breda</h1><p>Soort woning Appartement</p></main>"

    assert probe.extract_detail_property_type_candidates(html) == ("Appartement",)


def test_extracts_bouwgrond_when_present() -> None:
    html = '<meta property="og:description" content="Bouwgrond in verkoop">'

    assert probe.extract_detail_property_type_candidates(html) == ("Bouwgrond",)


def test_extracts_open_huis_as_badge_candidate_not_availability_status() -> None:
    html = '<section><span class="badge">Open huis</span><p>Status Beschikbaar</p></section>'

    result = probe.extract_detail_candidates(html)

    assert "Open huis" in result.badge_candidates
    assert "Open Huis" in result.badge_candidates
    assert result.property_type_candidates == ()
    assert any(signal.endswith(":badge:Open huis") for signal in result.evidence_signals)


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


def test_probe_module_does_not_write_outputs() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    written_methods = {"write_text", "write_bytes", "open"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in written_methods


def test_robots_false_avoids_detail_fetch(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: False)
    fetched_urls: list[str] = []

    def fetch_html(url: str) -> str:
        fetched_urls.append(url)
        return "<html>Woonhuis</html>"

    result = probe.run_ogonline_detail_property_type_probe_config(
        _config(),
        fetch_json=lambda url: json.dumps({"docs": [{"url": "/aanbod/wonen/breda/example-1/id-1"}]}),
        fetch_html=fetch_html,
        max_pages=1,
        max_samples=1,
    )

    assert fetched_urls == []
    assert result.samples_attempted == 0
    assert result.samples_succeeded == 0
    assert "api_blocked_by_robots" in result.warnings


def test_robots_false_avoids_detail_fetch_when_api_allowed(monkeypatch) -> None:
    def can_fetch(domain: str, path: str) -> bool:
        return domain == "cpl01.ogonline.nl"

    monkeypatch.setattr(robots_gate, "can_fetch", can_fetch)
    fetched_urls: list[str] = []

    def fetch_html(url: str) -> str:
        fetched_urls.append(url)
        return "<html>Woonhuis</html>"

    result = probe.run_ogonline_detail_property_type_probe_config(
        _config(),
        fetch_json=lambda url: json.dumps(
            {
                "docs": [
                    {
                        "url": "https://kinmakelaars.nl/aanbod/wonen/breda/example-1/id-1",
                        "address": "Example Street 1",
                        "isSales": True,
                        "status": "available",
                    }
                ]
            }
        ),
        fetch_html=fetch_html,
        max_pages=1,
        max_samples=1,
    )

    assert fetched_urls == []
    assert result.samples_attempted == 1
    assert result.samples_succeeded == 0
    assert result.samples[0].fetch_status == "blocked_by_robots"


def test_max_samples_is_respected() -> None:
    listings = tuple(_listing(index) for index in range(1, 9))

    selected = probe.select_detail_probe_listings(listings, max_samples=5)

    assert len(selected) == 5


def test_sample_selection_prioritizes_requested_status_mix() -> None:
    listings = (
        _listing(1, status="beschikbaar", property_type=""),
        _listing(2, status="beschikbaar", property_type=""),
        _listing(3, status="onder_bod"),
        _listing(4, status="unknown"),
        _listing(5, status="beschikbaar", price=900000, city="Tilburg"),
        _listing(6, status="beschikbaar", price=300000, city="Breda"),
    )

    selected = probe.select_detail_probe_listings(listings, max_samples=5)

    assert [listing.status for listing in selected] == [
        "beschikbaar",
        "beschikbaar",
        "onder_bod",
        "unknown",
        "beschikbaar",
    ]
    assert selected[-1].asking_price_eur == 900000
