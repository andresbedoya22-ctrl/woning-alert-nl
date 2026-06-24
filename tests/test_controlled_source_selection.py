from pathlib import Path
import ast
import sys


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.pilots.realworks_capture_pilot import CapturePilotSource  # noqa: E402
from domek_wonen.pilots.source_selection import (  # noqa: E402
    SourceSelectionCandidate,
    candidate_from_report_row,
    candidate_to_capture_pilot_source,
    select_realworks_pilot_sources_from_report,
)


def _row(
    source_id: str = "alpha.nl__tilburg",
    source_domain: str = "alpha.nl",
    listing_url: str = "https://www.alpha.nl/woningaanbod",
    parser_family_candidate: str = "realworks_public",
    delivery_mode: str = "realworks_public",
    access_status: str = "allowed",
    confidence: float = 0.86,
    priority_score: int = 10,
    **extra: object,
) -> dict[str, object]:
    return {
        "source_id": source_id,
        "source_domain": source_domain,
        "listing_url": listing_url,
        "parser_family_candidate": parser_family_candidate,
        "delivery_mode": delivery_mode,
        "access_status": access_status,
        "confidence": confidence,
        "priority_score": priority_score,
        **extra,
    }


def _report(*rows: dict[str, object]) -> dict[str, object]:
    return {"production_parser_ready_sources": list(rows)}


def test_selects_only_realworks_public_allowed_with_url_and_domain() -> None:
    result = select_realworks_pilot_sources_from_report(
        _report(
            _row(),
            _row(
                source_id="beta.nl__tilburg",
                source_domain="beta.nl",
                parser_family_candidate="wordpress_html_cards",
                delivery_mode="wordpress_html_cards",
            ),
        )
    )

    assert result.candidates_considered == 2
    assert result.candidates_selected == 1
    assert result.selected_sources == (
        CapturePilotSource(
            source_id="alpha.nl__tilburg",
            source_domain="alpha.nl",
            listing_url="https://www.alpha.nl/woningaanbod",
        ),
    )
    assert result.rejection_reasons == {"not_realworks_public": 1}


def test_excludes_non_realworks() -> None:
    result = select_realworks_pilot_sources_from_report(
        _report(_row(parser_family_candidate="kolibri_public", delivery_mode="kolibri_public"))
    )

    assert result.selected_sources == ()
    assert result.rejection_reasons["not_realworks_public"] == 1


def test_excludes_funda() -> None:
    result = select_realworks_pilot_sources_from_report(
        _report(_row(source_domain="funda.nl", listing_url="https://www.funda.nl/koop/tilburg/"))
    )

    assert result.selected_sources == ()
    assert result.rejection_reasons["funda_dependency"] == 1


def test_excludes_pararius() -> None:
    result = select_realworks_pilot_sources_from_report(
        _report(_row(source_domain="pararius.nl", listing_url="https://www.pararius.nl/koopwoningen/tilburg"))
    )

    assert result.selected_sources == ()
    assert result.rejection_reasons["pararius_dependency"] == 1


def test_excludes_blocked_permission_required_and_legal_review() -> None:
    result = select_realworks_pilot_sources_from_report(
        _report(
            _row(source_id="blocked", access_status="blocked"),
            _row(source_id="permission", access_status="permission_required"),
            _row(source_id="legal", access_status="legal_review"),
        )
    )

    assert result.selected_sources == ()
    assert result.rejection_reasons["blocked_or_permission_required"] == 3


def test_excludes_missing_listing_url() -> None:
    result = select_realworks_pilot_sources_from_report(_report(_row(listing_url="")))

    assert result.selected_sources == ()
    assert result.rejection_reasons["missing_listing_url"] == 1


def test_excludes_missing_source_domain() -> None:
    result = select_realworks_pilot_sources_from_report(_report(_row(source_domain="")))

    assert result.selected_sources == ()
    assert result.rejection_reasons["missing_source_domain"] == 1


def test_respects_max_sources_five() -> None:
    result = select_realworks_pilot_sources_from_report(
        _report(
            *[
                _row(
                    source_id=f"source-{index}",
                    source_domain=f"source-{index}.nl",
                    listing_url=f"https://source-{index}.nl/woningaanbod",
                )
                for index in range(7)
            ]
        )
    )

    assert result.candidates_selected == 5
    assert len(result.selected_sources) == 5


def test_max_sources_lte_zero_returns_empty_with_warning() -> None:
    result = select_realworks_pilot_sources_from_report(_report(_row()), max_sources=0)

    assert result.selected_sources == ()
    assert result.candidates_considered == 0
    assert result.warnings == ("max_sources_must_be_positive",)


def test_sorts_allowed_before_limited() -> None:
    result = select_realworks_pilot_sources_from_report(
        _report(
            _row(source_id="limited", source_domain="limited.nl", access_status="limited", confidence=0.99),
            _row(source_id="allowed", source_domain="allowed.nl", access_status="allowed", confidence=0.50),
        )
    )

    assert [source.source_id for source in result.selected_sources] == ["allowed", "limited"]


def test_sorts_by_confidence_descending() -> None:
    result = select_realworks_pilot_sources_from_report(
        _report(
            _row(source_id="low", source_domain="low.nl", confidence=0.20),
            _row(source_id="high", source_domain="high.nl", confidence=0.90),
        )
    )

    assert [source.source_id for source in result.selected_sources] == ["high", "low"]


def test_converts_candidate_to_capture_pilot_source() -> None:
    candidate = SourceSelectionCandidate(
        source_id="alpha",
        source_domain="alpha.nl",
        listing_url="https://alpha.nl/woningaanbod",
        parser_family_candidate="realworks_public",
        delivery_mode="realworks_public",
        access_status="allowed",
    )

    source = candidate_to_capture_pilot_source(candidate)

    assert source == CapturePilotSource(
        source_id="alpha",
        source_domain="alpha.nl",
        listing_url="https://alpha.nl/woningaanbod",
    )


def test_tolerates_missing_section_with_empty_selection_and_warning() -> None:
    result = select_realworks_pilot_sources_from_report({"source_intelligence": {}})

    assert result.selected_sources == ()
    assert result.candidates_considered == 0
    assert result.warnings == ("production_parser_ready_sources_missing", "no_candidate_rows")


def test_candidate_from_report_row_accepts_aanbod_url_alias() -> None:
    candidate = candidate_from_report_row(
        {
            "source_id": "alpha",
            "root_domain": "www.alpha.nl",
            "aanbod_url": "https://www.alpha.nl/woningaanbod",
            "parser_family_candidate": "realworks_public",
            "delivery_mode": "realworks_public",
            "legal_status": "allowed_official_source",
            "confidence_score": "75",
            "score": "90",
        }
    )

    assert candidate is not None
    assert candidate.source_domain == "alpha.nl"
    assert candidate.listing_url == "https://www.alpha.nl/woningaanbod"
    assert candidate.access_status == "allowed"
    assert candidate.confidence == 0.75
    assert candidate.priority_score == 90


def test_source_selection_module_has_no_network_or_browser_imports() -> None:
    module_path = BASE_DIR / "scraper" / "src" / "domek_wonen" / "pilots" / "source_selection.py"
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
    assert "playwright" not in imported_roots
    assert "selenium" not in imported_roots
