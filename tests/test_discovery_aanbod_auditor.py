from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.discovery.aanbod_auditor import AanbodAuditor
from domek_wonen.discovery.models import SourceCandidate


VALID_LISTING_HTML = """
<html>
  <head><title>Woningaanbod</title></head>
  <body>
    <h1>Aanbod</h1>
    <div class="card">Vraagprijs € 350.000 k.k. Appartement 3 kamers woonoppervlakte 90 m2</div>
    <div class="card">Prijs € 425.000 kosten koper woning 4 slaapkamers beschikbaar</div>
    <div class="card">Onder bod tussenwoning 5 kamers woonoppervlakte 120 m2</div>
  </body>
</html>
"""


class _FakeResponse:
    def __init__(self, url: str, status: int, content_type: str) -> None:
        self.url = url
        self.status = status
        self.headers = {"content-type": content_type}


class _FakePage:
    def __init__(self, responses: dict[str, dict[str, str | int]]) -> None:
        self._responses = {key.rstrip("/"): value for key, value in responses.items()}
        self.url = ""
        self._html = ""

    def goto(self, url: str, wait_until: str, timeout: int):
        normalized = url.rstrip("/")
        payload = self._responses.get(normalized)
        if payload is None:
            self.url = normalized
            self._html = ""
            return _FakeResponse(normalized, 404, "text/html")
        self.url = normalized
        self._html = str(payload["html"])
        return _FakeResponse(
            normalized,
            int(payload.get("status", 200)),
            str(payload.get("content_type", "text/html")),
        )

    def content(self) -> str:
        return self._html


class _FakeContext:
    def __init__(self, responses: dict[str, dict[str, str | int]]) -> None:
        self._responses = responses

    def new_page(self) -> _FakePage:
        return _FakePage(self._responses)

    def close(self) -> None:
        return None


class _FakeBrowser:
    def __init__(self, responses: dict[str, dict[str, str | int]]) -> None:
        self._responses = responses

    def new_context(self) -> _FakeContext:
        return _FakeContext(self._responses)

    def close(self) -> None:
        return None


class _FakePlaywrightManager:
    def __init__(self, responses: dict[str, dict[str, str | int]]) -> None:
        self.chromium = self
        self._responses = responses

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def launch(self, headless: bool) -> _FakeBrowser:
        assert headless is True
        return _FakeBrowser(self._responses)


def _patch_playwright(monkeypatch, responses: dict[str, dict[str, str | int]]) -> None:
    monkeypatch.setattr(
        "domek_wonen.discovery.aanbod_auditor.sync_playwright",
        lambda: _FakePlaywrightManager(responses),
    )


def test_auditor_finds_homepage_aanbod_link(monkeypatch) -> None:
    _patch_playwright(
        monkeypatch,
        {
            "https://example.nl": {
                "status": 200,
                "content_type": "text/html",
                "html": '<html><head><title>Makelaar</title></head><body><a href="/aanbod">Aanbod</a></body></html>',
            },
            "https://example.nl/aanbod": {"status": 200, "content_type": "text/html", "html": VALID_LISTING_HTML},
            "https://example.nl/sitemap.xml": {"status": 404, "content_type": "application/xml", "html": ""},
        },
    )
    candidate = SourceCandidate(
        office_name="Example Makelaardij",
        website="https://example.nl",
        root_domain="example.nl",
        gemeente="Breda",
        aanbod_url_quality="missing",
    )

    attempts = AanbodAuditor(confidence_threshold=85).audit_candidates([candidate], max_audited_sites=1)

    assert len(attempts) == 1
    assert attempts[0].final_status == "valid"
    assert attempts[0].final_aanbod_url == "https://example.nl/aanbod"
    assert attempts[0].final_page_type == "listing_index"
    assert candidate.aanbod_url == "https://example.nl/aanbod"
    assert candidate.aanbod_url_quality == "valid"
    assert candidate.aanbod_detection_method == "browser_audit"


def test_auditor_uses_sitemap_as_discovery_not_final_url(monkeypatch) -> None:
    _patch_playwright(
        monkeypatch,
        {
            "https://example.nl": {
                "status": 200,
                "content_type": "text/html",
                "html": "<html><head><title>Home</title></head><body>Welkom</body></html>",
            },
            "https://example.nl/sitemap.xml": {
                "status": 200,
                "content_type": "application/xml",
                "html": """
                    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                      <url><loc>https://example.nl/koopwoningen</loc></url>
                    </urlset>
                """,
            },
            "https://example.nl/koopwoningen": {"status": 200, "content_type": "text/html", "html": VALID_LISTING_HTML},
        },
    )
    candidate = SourceCandidate(
        office_name="Example Makelaardij",
        website="https://example.nl",
        root_domain="example.nl",
        gemeente="Tilburg",
        aanbod_url_quality="missing",
    )

    attempts = AanbodAuditor(confidence_threshold=85).audit_candidates([candidate], max_audited_sites=1)

    assert attempts[0].final_status == "valid"
    assert attempts[0].final_aanbod_url == "https://example.nl/koopwoningen"
    assert attempts[0].detection_method == "sitemap"


def test_auditor_rejects_taxatie_page(monkeypatch) -> None:
    _patch_playwright(
        monkeypatch,
        {
            "https://example.nl": {
                "status": 200,
                "content_type": "text/html",
                "html": '<html><head><title>Home</title></head><body><a href="/taxatie">Taxatie</a></body></html>',
            },
            "https://example.nl/sitemap.xml": {"status": 404, "content_type": "application/xml", "html": ""},
            "https://example.nl/taxatie": {
                "status": 200,
                "content_type": "text/html",
                "html": "<html><body><h1>Taxatie</h1></body></html>",
            },
        },
    )
    candidate = SourceCandidate(
        office_name="Example Makelaardij",
        website="https://example.nl",
        root_domain="example.nl",
        gemeente="Eindhoven",
        aanbod_url_quality="missing",
    )

    attempts = AanbodAuditor(confidence_threshold=85).audit_candidates([candidate], max_audited_sites=1)

    assert attempts[0].final_status == "missing"
    assert attempts[0].final_aanbod_url == ""
    assert candidate.aanbod_url_quality == "missing"


def test_bedrijfshuisvesting_page_is_not_valid_residential(monkeypatch) -> None:
    _patch_playwright(
        monkeypatch,
        {
            "https://hofstedebedrijfshuisvesting.nl": {
                "status": 200,
                "content_type": "text/html",
                "html": '<html><body><a href="/aanbod">Aanbod</a></body></html>',
            },
            "https://hofstedebedrijfshuisvesting.nl/aanbod": {
                "status": 200,
                "content_type": "text/html",
                "html": """
                    <html><body>
                    <h1>Bedrijfshuisvesting aanbod</h1>
                    <div>Bedrijfsruimte en kantoorruimte op bedrijventerrein.</div>
                    </body></html>
                """,
            },
            "https://hofstedebedrijfshuisvesting.nl/sitemap.xml": {"status": 404, "content_type": "application/xml", "html": ""},
        },
    )
    candidate = SourceCandidate(
        office_name="Hofstede",
        website="https://hofstedebedrijfshuisvesting.nl",
        root_domain="hofstedebedrijfshuisvesting.nl",
        gemeente="Breda",
        aanbod_url_quality="missing",
    )

    attempts = AanbodAuditor(confidence_threshold=85).audit_candidates([candidate], max_audited_sites=1)

    assert attempts[0].final_status == "rejected"
    assert attempts[0].final_page_type == "commercial_listing"
    assert attempts[0].page_quality_reason == "commercial_only"
    assert candidate.aanbod_url_quality == "missing"


def test_bedrijfsaanbod_path_never_becomes_valid(monkeypatch) -> None:
    _patch_playwright(
        monkeypatch,
        {
            "https://vandenboschmakelaars.com": {
                "status": 200,
                "content_type": "text/html",
                "html": '<html><body><a href="/bedrijfsaanbod">Bedrijfsaanbod</a></body></html>',
            },
            "https://vandenboschmakelaars.com/bedrijfsaanbod": {
                "status": 200,
                "content_type": "text/html",
                "html": """
                    <html><head><title>Bedrijfsaanbod</title></head><body>
                    <h1>Bedrijfsaanbod</h1>
                    <div>Appartement woning vraagprijs k.k. woonoppervlakte slaapkamers.</div>
                    </body></html>
                """,
            },
            "https://vandenboschmakelaars.com/sitemap.xml": {"status": 404, "content_type": "application/xml", "html": ""},
        },
    )
    candidate = SourceCandidate(
        office_name="Van den Bosch",
        website="https://vandenboschmakelaars.com",
        root_domain="vandenboschmakelaars.com",
        gemeente="Breda",
        aanbod_url_quality="missing",
    )

    attempts = AanbodAuditor(confidence_threshold=85).audit_candidates([candidate], max_audited_sites=1)

    assert attempts[0].final_status == "rejected"
    assert attempts[0].final_page_type == "commercial_listing"
    assert attempts[0].commercial_hard_block is True
    assert attempts[0].commercial_block_reason == "path:bedrijfsaanbod"
    assert attempts[0].rejection_reason == "commercial_only"
    assert candidate.aanbod_url_quality == "missing"


def test_property_detail_page_is_suspect_not_valid(monkeypatch) -> None:
    _patch_playwright(
        monkeypatch,
        {
            "https://example.nl": {
                "status": 200,
                "content_type": "text/html",
                "html": '<html><body><a href="/aanbod/veen/waterfront">Waterfront</a></body></html>',
            },
            "https://example.nl/aanbod/veen/waterfront": {
                "status": 200,
                "content_type": "text/html",
                "html": """
                    <html><body>
                    <h1>Waterfront appartement</h1>
                    <div>Vraagprijs € 450.000 k.k.</div>
                    <div>Woonoppervlakte 112 m2, slaapkamers 3, kenmerken en beschrijving.</div>
                    </body></html>
                """,
            },
            "https://example.nl/sitemap.xml": {"status": 404, "content_type": "application/xml", "html": ""},
        },
    )
    candidate = SourceCandidate(
        office_name="Example Makelaardij",
        website="https://example.nl",
        root_domain="example.nl",
        gemeente="Breda",
        aanbod_url_quality="missing",
    )

    attempts = AanbodAuditor(confidence_threshold=85).audit_candidates([candidate], max_audited_sites=1)

    assert attempts[0].final_status == "suspect"
    assert attempts[0].final_page_type == "property_detail"
    assert candidate.aanbod_url_quality == "suspect"


def test_duplicate_valid_results_are_marked(monkeypatch) -> None:
    _patch_playwright(
        monkeypatch,
        {
            "https://example.nl": {
                "status": 200,
                "content_type": "text/html",
                "html": '<html><body><a href="/aanbod">Aanbod</a></body></html>',
            },
            "https://example.nl/aanbod": {"status": 200, "content_type": "text/html", "html": VALID_LISTING_HTML},
            "https://example.nl/sitemap.xml": {"status": 404, "content_type": "application/xml", "html": ""},
        },
    )
    candidates = [
        SourceCandidate(
            office_name="Example Breda",
            website="https://example.nl",
            root_domain="example.nl",
            gemeente="Breda",
            aanbod_url_quality="missing",
        ),
        SourceCandidate(
            office_name="Example Tilburg",
            website="https://example.nl",
            root_domain="example.nl",
            gemeente="Tilburg",
            aanbod_url_quality="missing",
        ),
    ]

    attempts = AanbodAuditor(confidence_threshold=85).audit_candidates(candidates, max_audited_sites=2)

    assert len(attempts) == 2
    assert attempts[0].final_status == "valid"
    assert attempts[0].is_duplicate_audit_result is False
    assert attempts[1].final_status == "valid"
    assert attempts[1].is_duplicate_audit_result is True
