from pathlib import Path
import csv
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.discovery.models import SourceCandidate
from domek_wonen.discovery.source_master_builder import build_source_master_rows, write_source_master


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
