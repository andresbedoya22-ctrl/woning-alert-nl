from pathlib import Path
import csv
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.discovery.models import SourceCandidate
from domek_wonen.discovery.source_master_builder import (
    build_source_master_from_csv,
    build_source_master_rows,
    write_source_master,
)
from scripts.build_source_master import main as build_source_master_main


def test_valid_source_is_active_true(tmp_path) -> None:
    rows = build_source_master_rows(
        [
            SourceCandidate(
                office_name="Alpha",
                root_domain="alpha.nl",
                website="https://alpha.nl",
                gemeente="Breda",
                provincie="Noord-Brabant",
                source_origin="seed",
                aanbod_url="https://alpha.nl/aanbod",
                aanbod_url_quality="valid",
            )
        ],
        run_timestamp="20260613T000000Z",
    )

    assert rows[0]["legal_status"] == "allowed_official_source"
    assert rows[0]["is_active"] == "true"


def test_suspect_source_is_inactive_and_needs_review(tmp_path) -> None:
    rows = build_source_master_rows(
        [
            SourceCandidate(
                office_name="Beta",
                root_domain="beta.nl",
                website="https://beta.nl",
                gemeente="Tilburg",
                provincie="Noord-Brabant",
                source_origin="seed",
                aanbod_url_quality="suspect",
            )
        ],
        run_timestamp="20260613T000000Z",
    )

    assert rows[0]["is_active"] == "false"
    assert rows[0]["needs_review"] == "true"


def test_source_master_csv_is_created(tmp_path) -> None:
    path = tmp_path / "makelaar_sources_master.csv"
    rows = build_source_master_rows(
        [
            SourceCandidate(
                office_name="Gamma",
                root_domain="gamma.nl",
                website="https://gamma.nl",
                gemeente="Eindhoven",
                provincie="Noord-Brabant",
                source_origin="seed",
                aanbod_url_quality="missing",
            )
        ],
        run_timestamp="20260613T000000Z",
    )

    write_source_master(path, rows)

    with path.open("r", encoding="utf-8", newline="") as handle:
        written = list(csv.DictReader(handle))
    assert len(written) == 1
    assert written[0]["office_name"] == "Gamma"


def test_build_source_master_from_discovered_sources_csv(tmp_path) -> None:
    discovered_path = tmp_path / "discovered_sources.csv"
    discovered_path.write_text(
        "\n".join(
            [
                "office_name,website,root_domain,gemeente,provincie,aanbod_url,aanbod_url_quality,candidate_score,source_origin",
                "Delta Makelaars,https://delta.nl,delta.nl,Breda,Noord-Brabant,https://delta.nl/aanbod,valid,88,",
                "Echo Wonen,https://echo.nl,echo.nl,Tilburg,Noord-Brabant,,missing,,seed",
            ]
        ),
        encoding="utf-8",
    )

    rows = build_source_master_from_csv(
        discovered_path,
        run_timestamp="20260614T120000Z",
        default_run_id="latest",
    )

    assert len(rows) == 2
    assert rows[0]["source_origin"] == "source_discovery"
    assert rows[0]["score"] == "88"
    assert rows[0]["run_id"] == "latest"
    assert rows[1]["score"] == "0"
    assert rows[1]["needs_review"] == "true"
    assert rows[1]["last_seen_at"] == "20260614T120000Z"


def test_build_source_master_script_writes_output(tmp_path) -> None:
    discovered_path = tmp_path / "discovered_sources.csv"
    output_path = tmp_path / "makelaar_sources_master.csv"
    discovered_path.write_text(
        "\n".join(
            [
                "office_name,website,root_domain,gemeente,province,aanbod_url,aanbod_url_quality,score,needs_review,run_id",
                "Foxtrot,https://foxtrot.nl,foxtrot.nl,Eindhoven,Noord-Brabant,https://foxtrot.nl/aanbod,valid,91,false,run-123",
            ]
        ),
        encoding="utf-8",
    )

    exit_code = build_source_master_main(
        [
            "--input",
            str(discovered_path),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    with output_path.open("r", encoding="utf-8", newline="") as handle:
        written = list(csv.DictReader(handle))
    assert written[0]["office_name"] == "Foxtrot"
    assert written[0]["run_id"] == "run-123"
