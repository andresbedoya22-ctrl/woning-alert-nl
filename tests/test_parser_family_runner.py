from pathlib import Path
import ast
import sys


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.parsers import ParserFamilyResult, ParserFamilyRunner, ParserInput, run_parser_family
import domek_wonen.parsers.runner as runner_module
from domek_wonen.sources.delivery_fingerprint import DeliveryFingerprintResult


def _parser_input(content: str | None = None) -> ParserInput:
    if content is None:
        content = (BASE_DIR / "tests" / "fixtures" / "parsers" / "realworks_listing_fixture.html").read_text(
            encoding="utf-8"
        )
    return ParserInput(
        source_id="example-realworks",
        source_domain="example.nl",
        source_url="https://example.nl/aanbod/woningaanbod",
        content=content,
    )


def _fingerprint(
    *,
    delivery_mode: str = "realworks_public",
    parser_family_candidate: str = "realworks_public",
    can_proceed_to_parser_family: bool = True,
) -> DeliveryFingerprintResult:
    return DeliveryFingerprintResult(
        source_id="example-realworks",
        source_domain="example.nl",
        access_status="allowed",
        delivery_mode=delivery_mode,
        parser_family_candidate=parser_family_candidate,
        confidence=0.86,
        evidence_signals=("realworks",),
        blocking_signals=(),
        recommended_action="build_source_config",
        can_proceed_to_parser_family=can_proceed_to_parser_family,
        reason="realworks_evidence",
    )


class _ExplodingParserFamily:
    def parse_listing_page(self, parser_input: ParserInput) -> ParserFamilyResult:
        raise AssertionError("parser family should not be executed")


def test_runner_executes_realworks_family_when_fingerprint_allows_realworks_public() -> None:
    result = ParserFamilyRunner().run(_fingerprint(), _parser_input())

    assert isinstance(result, ParserFamilyResult)
    assert result.parser_family == "realworks_public"
    assert len(result.listings) == 3


def test_runner_returns_listings_from_realworks_fixture() -> None:
    result = ParserFamilyRunner().run(_fingerprint(), _parser_input())

    assert [listing.canonical_url for listing in result.listings] == [
        "https://example.nl/aanbod/woningaanbod/breda/koop/huis-1001-zonnelaan-12",
        "https://example.nl/aanbod/woningaanbod/tilburg/koop/huis-1002-spoorstraat-8",
        "https://example.nl/woningaanbod/koop/eindhoven/appartement-1003",
    ]


def test_runner_does_not_execute_parser_when_fingerprint_disallows_parser_family(monkeypatch) -> None:
    monkeypatch.setattr(runner_module, "RealworksParserFamily", _ExplodingParserFamily)

    result = ParserFamilyRunner().run(
        _fingerprint(can_proceed_to_parser_family=False),
        _parser_input(),
    )

    assert result.parser_family == "realworks_public"
    assert result.listings == ()
    assert result.rejected_count == 0
    assert result.warning_count >= 1
    assert "parser_family_not_allowed" in result.warnings


def test_runner_does_not_execute_parser_for_unsupported_parser_family(monkeypatch) -> None:
    monkeypatch.setattr(runner_module, "RealworksParserFamily", _ExplodingParserFamily)

    result = ParserFamilyRunner().run(
        _fingerprint(delivery_mode="json_ld", parser_family_candidate="json_ld"),
        _parser_input(),
    )

    assert result.parser_family == "json_ld"
    assert result.listings == ()
    assert result.rejected_count == 0


def test_runner_returns_warning_for_unsupported_parser_family() -> None:
    result = ParserFamilyRunner().run(
        _fingerprint(delivery_mode="json_ld", parser_family_candidate="json_ld"),
        _parser_input(),
    )

    assert result.warning_count >= 1
    assert "unsupported_parser_family" in result.warnings


def test_runner_returns_warning_for_empty_parser_input(monkeypatch) -> None:
    monkeypatch.setattr(runner_module, "RealworksParserFamily", _ExplodingParserFamily)

    result = ParserFamilyRunner().run(_fingerprint(), _parser_input(content=""))

    assert result.parser_family == "realworks_public"
    assert result.listings == ()
    assert result.rejected_count == 0
    assert result.warning_count >= 1
    assert "empty_parser_input" in result.warnings


def test_runner_preserves_source_id_and_source_domain_in_result() -> None:
    result = ParserFamilyRunner().run(_fingerprint(), _parser_input())

    assert result.source_id == "example-realworks"
    assert result.source_domain == "example.nl"
    assert {listing.source_id for listing in result.listings} == {"example-realworks"}
    assert {listing.source_domain for listing in result.listings} == {"example.nl"}


def test_run_parser_family_helper_matches_runner_run() -> None:
    fingerprint = _fingerprint()
    parser_input = _parser_input()

    assert run_parser_family(fingerprint, parser_input) == ParserFamilyRunner().run(fingerprint, parser_input)


def test_parser_family_runner_module_has_no_network_or_browser_imports() -> None:
    module_path = BASE_DIR / "scraper" / "src" / "domek_wonen" / "parsers" / "runner.py"
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    imported_roots = {module.split(".")[0] for module in imported_modules}
    assert "requests" not in imported_roots
    assert "httpx" not in imported_roots
    assert "urllib" not in imported_roots
    assert "playwright" not in imported_roots
    assert "selenium" not in imported_roots
    assert "WebsiteFetcher" not in source
