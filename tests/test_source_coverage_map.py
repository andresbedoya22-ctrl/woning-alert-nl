from pathlib import Path
import csv
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.diagnostics.source_coverage_map import CSV_FIELDNAMES, run_source_coverage_map
from scripts.run_source_coverage_map import main as source_coverage_main


SOURCE_MASTER_FIELDNAMES = [
    "source_id",
    "office_name",
    "root_domain",
    "website",
    "gemeente",
    "province",
    "aanbod_url",
    "legal_status",
    "last_seen_at",
    "run_id",
]
PLATFORM_FINGERPRINT_FIELDNAMES = [
    "source_id",
    "office_name",
    "root_domain",
    "website_url",
    "aanbod_url",
    "detected_platform",
    "confidence",
    "evidence",
    "fetch_status",
    "error",
]
PROPERTY_CANDIDATE_FIELDNAMES = [
    "source_id",
    "root_domain",
    "source_url",
    "property_url",
    "city_raw",
    "gemeente",
    "discovery_run_id",
]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_builds_inventory_from_local_fixtures(tmp_path: Path) -> None:
    source_master_path = tmp_path / "makelaar_sources_master.csv"
    platform_fingerprint_path = tmp_path / "platform_fingerprint_results.csv"
    property_discovery_run_dir = tmp_path / "property_discovery" / "20260616T175850Z"
    _write_csv(
        source_master_path,
        SOURCE_MASTER_FIELDNAMES,
        [
            {
                "source_id": "alpha.nl__tilburg",
                "office_name": "Alpha Tilburg",
                "root_domain": "alpha.nl",
                "website": "https://alpha.nl",
                "gemeente": "Tilburg",
                "province": "Noord-Brabant",
                "aanbod_url": "https://alpha.nl/aanbod/woningaanbod",
                "legal_status": "allowed_official_source",
                "last_seen_at": "20260614T122022Z",
                "run_id": "20260614T122022Z",
            },
            {
                "source_id": "beta.nl__tilburg",
                "office_name": "Beta Tilburg",
                "root_domain": "beta.nl",
                "website": "https://beta.nl",
                "gemeente": "Tilburg",
                "province": "Noord-Brabant",
                "aanbod_url": "https://beta.nl/aanbod",
                "legal_status": "needs_manual_review",
                "last_seen_at": "20260614T122022Z",
                "run_id": "20260614T122022Z",
            },
        ],
    )
    _write_csv(
        platform_fingerprint_path,
        PLATFORM_FINGERPRINT_FIELDNAMES,
        [
            {
                "source_id": "alpha.nl__tilburg",
                "office_name": "Alpha Tilburg",
                "root_domain": "alpha.nl",
                "website_url": "https://alpha.nl",
                "aanbod_url": "https://alpha.nl/aanbod/woningaanbod",
                "detected_platform": "realworks",
                "confidence": "0.95",
                "evidence": "signal:realworks",
                "fetch_status": "homepage_ok;aanbod_ok",
                "error": "",
            },
            {
                "source_id": "beta.nl__tilburg",
                "office_name": "Beta Tilburg",
                "root_domain": "beta.nl",
                "website_url": "https://beta.nl",
                "aanbod_url": "https://beta.nl/aanbod",
                "detected_platform": "custom",
                "confidence": "0.55",
                "evidence": "signal:custom",
                "fetch_status": "homepage_ok;aanbod_ok",
                "error": "",
            },
        ],
    )
    _write_csv(
        property_discovery_run_dir / "property_candidates.csv",
        PROPERTY_CANDIDATE_FIELDNAMES,
        [
            {
                "source_id": "alpha.nl__tilburg",
                "root_domain": "alpha.nl",
                "source_url": "https://alpha.nl/aanbod/woningaanbod",
                "property_url": "https://alpha.nl/object/1",
                "city_raw": "Tilburg",
                "gemeente": "Tilburg",
                "discovery_run_id": "20260616T175850Z",
            }
        ],
    )

    result = run_source_coverage_map(
        city="Tilburg",
        province="noord-brabant",
        source_master_path=source_master_path,
        platform_fingerprint_path=platform_fingerprint_path,
        property_discovery_run_dir=property_discovery_run_dir,
        output_base_dir=tmp_path / "out",
    )

    assert result.total_sources_for_city == 2
    assert result.inventory_output_path.exists()
    assert result.report_path.exists()

    with result.inventory_output_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert list(rows[0].keys()) == CSV_FIELDNAMES
    assert {row["source_name"] for row in rows} == {"Alpha Tilburg", "Beta Tilburg"}


def test_realworks_supported_when_existing_parser_supports_platform(tmp_path: Path) -> None:
    source_master_path = tmp_path / "makelaar_sources_master.csv"
    platform_fingerprint_path = tmp_path / "platform_fingerprint_results.csv"
    _write_csv(
        source_master_path,
        SOURCE_MASTER_FIELDNAMES,
        [
            {
                "source_id": "alpha.nl__tilburg",
                "office_name": "Alpha Tilburg",
                "root_domain": "alpha.nl",
                "website": "https://alpha.nl",
                "gemeente": "Tilburg",
                "province": "Noord-Brabant",
                "aanbod_url": "https://alpha.nl/aanbod/woningaanbod",
                "legal_status": "allowed_official_source",
                "last_seen_at": "",
                "run_id": "run-1",
            }
        ],
    )
    _write_csv(
        platform_fingerprint_path,
        PLATFORM_FINGERPRINT_FIELDNAMES,
        [
            {
                "source_id": "alpha.nl__tilburg",
                "office_name": "Alpha Tilburg",
                "root_domain": "alpha.nl",
                "website_url": "https://alpha.nl",
                "aanbod_url": "https://alpha.nl/aanbod/woningaanbod",
                "detected_platform": "realworks",
                "confidence": "0.95",
                "evidence": "signal:realworks",
                "fetch_status": "homepage_ok;aanbod_ok",
                "error": "",
            }
        ],
    )

    result = run_source_coverage_map(
        city="Tilburg",
        province="Noord-Brabant",
        source_master_path=source_master_path,
        platform_fingerprint_path=platform_fingerprint_path,
        property_discovery_run_dir=tmp_path / "missing",
        output_base_dir=tmp_path / "out",
    )

    row = result.inventory_rows[0]
    assert row["platform_guess"] == "realworks"
    assert row["supported_by_existing_parser"] == "true"
    assert row["operational_status"] == "supported"


def test_recommends_add_supported_source_to_discovery_when_supported_not_in_discovery_exists(tmp_path: Path) -> None:
    source_master_path = tmp_path / "makelaar_sources_master.csv"
    platform_fingerprint_path = tmp_path / "platform_fingerprint_results.csv"
    _write_csv(
        source_master_path,
        SOURCE_MASTER_FIELDNAMES,
        [
            {
                "source_id": "alpha.nl__tilburg",
                "office_name": "Alpha Tilburg",
                "root_domain": "alpha.nl",
                "website": "https://alpha.nl",
                "gemeente": "Tilburg",
                "province": "Noord-Brabant",
                "aanbod_url": "https://alpha.nl/aanbod/woningaanbod",
                "legal_status": "allowed_official_source",
                "last_seen_at": "",
                "run_id": "run-1",
            }
        ],
    )
    _write_csv(
        platform_fingerprint_path,
        PLATFORM_FINGERPRINT_FIELDNAMES,
        [
            {
                "source_id": "alpha.nl__tilburg",
                "office_name": "Alpha Tilburg",
                "root_domain": "alpha.nl",
                "website_url": "https://alpha.nl",
                "aanbod_url": "https://alpha.nl/aanbod/woningaanbod",
                "detected_platform": "realworks",
                "confidence": "0.95",
                "evidence": "signal:realworks",
                "fetch_status": "homepage_ok;aanbod_ok",
                "error": "",
            }
        ],
    )

    result = run_source_coverage_map(
        city="Tilburg",
        province="Noord-Brabant",
        source_master_path=source_master_path,
        platform_fingerprint_path=platform_fingerprint_path,
        property_discovery_run_dir=tmp_path / "missing",
        output_base_dir=tmp_path / "out",
    )

    assert result.supported_not_in_discovery == 1
    assert result.recommended_next_bottleneck == "add_supported_source_to_discovery"
    assert "supported_not_in_discovery: 1" in result.report_path.read_text(encoding="utf-8")


def test_classifies_unknown_when_no_platform_evidence_exists(tmp_path: Path) -> None:
    source_master_path = tmp_path / "makelaar_sources_master.csv"
    _write_csv(
        source_master_path,
        SOURCE_MASTER_FIELDNAMES,
        [
            {
                "source_id": "gamma.nl__tilburg",
                "office_name": "Gamma Tilburg",
                "root_domain": "gamma.nl",
                "website": "https://gamma.nl",
                "gemeente": "Tilburg",
                "province": "Noord-Brabant",
                "aanbod_url": "",
                "legal_status": "missing",
                "last_seen_at": "",
                "run_id": "run-1",
            }
        ],
    )

    result = run_source_coverage_map(
        city="Tilburg",
        province="Noord-Brabant",
        source_master_path=source_master_path,
        platform_fingerprint_path=tmp_path / "missing.csv",
        property_discovery_run_dir=tmp_path / "missing",
        output_base_dir=tmp_path / "out",
    )

    row = result.inventory_rows[0]
    assert row["platform_guess"] == "unknown"
    assert row["operational_status"] == "unknown"


def test_recommends_investigate_unknown_platform_when_no_supported_not_in_discovery(tmp_path: Path) -> None:
    source_master_path = tmp_path / "makelaar_sources_master.csv"
    _write_csv(
        source_master_path,
        SOURCE_MASTER_FIELDNAMES,
        [
            {
                "source_id": "gamma.nl__tilburg",
                "office_name": "Gamma Tilburg",
                "root_domain": "gamma.nl",
                "website": "https://gamma.nl",
                "gemeente": "Tilburg",
                "province": "Noord-Brabant",
                "aanbod_url": "",
                "legal_status": "missing",
                "last_seen_at": "",
                "run_id": "run-1",
            }
        ],
    )

    result = run_source_coverage_map(
        city="Tilburg",
        province="Noord-Brabant",
        source_master_path=source_master_path,
        platform_fingerprint_path=tmp_path / "missing.csv",
        property_discovery_run_dir=tmp_path / "missing",
        output_base_dir=tmp_path / "out",
    )

    assert result.supported_not_in_discovery == 0
    assert result.recommended_next_bottleneck == "investigate_unknown_platform"


def test_marks_included_in_discovery_when_domain_is_present(tmp_path: Path) -> None:
    source_master_path = tmp_path / "makelaar_sources_master.csv"
    _write_csv(
        source_master_path,
        SOURCE_MASTER_FIELDNAMES,
        [
            {
                "source_id": "alpha.nl__tilburg",
                "office_name": "Alpha Tilburg",
                "root_domain": "alpha.nl",
                "website": "https://alpha.nl",
                "gemeente": "Tilburg",
                "province": "Noord-Brabant",
                "aanbod_url": "https://alpha.nl/aanbod/woningaanbod",
                "legal_status": "allowed_official_source",
                "last_seen_at": "",
                "run_id": "run-1",
            }
        ],
    )
    property_discovery_run_dir = tmp_path / "property_discovery" / "20260616T175850Z"
    _write_csv(
        property_discovery_run_dir / "property_candidates.csv",
        PROPERTY_CANDIDATE_FIELDNAMES,
        [
            {
                "source_id": "another-id",
                "root_domain": "alpha.nl",
                "source_url": "https://alpha.nl/aanbod/woningaanbod",
                "property_url": "https://alpha.nl/object/1",
                "city_raw": "Tilburg",
                "gemeente": "Tilburg",
                "discovery_run_id": "20260616T175850Z",
            }
        ],
    )

    result = run_source_coverage_map(
        city="Tilburg",
        province="Noord-Brabant",
        source_master_path=source_master_path,
        platform_fingerprint_path=tmp_path / "missing.csv",
        property_discovery_run_dir=property_discovery_run_dir,
        output_base_dir=tmp_path / "out",
    )

    assert result.inventory_rows[0]["included_in_discovery"] == "true"


def test_fallback_recommends_improve_existing_source_recovery(tmp_path: Path) -> None:
    source_master_path = tmp_path / "makelaar_sources_master.csv"
    platform_fingerprint_path = tmp_path / "platform_fingerprint_results.csv"
    property_discovery_run_dir = tmp_path / "property_discovery" / "20260616T175850Z"
    _write_csv(
        source_master_path,
        SOURCE_MASTER_FIELDNAMES,
        [
            {
                "source_id": "alpha.nl__tilburg",
                "office_name": "Alpha Tilburg",
                "root_domain": "alpha.nl",
                "website": "https://alpha.nl",
                "gemeente": "Tilburg",
                "province": "Noord-Brabant",
                "aanbod_url": "https://alpha.nl/aanbod/woningaanbod",
                "legal_status": "allowed_official_source",
                "last_seen_at": "",
                "run_id": "run-1",
            }
        ],
    )
    _write_csv(
        platform_fingerprint_path,
        PLATFORM_FINGERPRINT_FIELDNAMES,
        [
            {
                "source_id": "alpha.nl__tilburg",
                "office_name": "Alpha Tilburg",
                "root_domain": "alpha.nl",
                "website_url": "https://alpha.nl",
                "aanbod_url": "https://alpha.nl/aanbod/woningaanbod",
                "detected_platform": "realworks",
                "confidence": "0.95",
                "evidence": "signal:realworks",
                "fetch_status": "homepage_ok;aanbod_ok",
                "error": "",
            }
        ],
    )
    _write_csv(
        property_discovery_run_dir / "property_candidates.csv",
        PROPERTY_CANDIDATE_FIELDNAMES,
        [
            {
                "source_id": "alpha.nl__tilburg",
                "root_domain": "alpha.nl",
                "source_url": "https://alpha.nl/aanbod/woningaanbod",
                "property_url": "https://alpha.nl/object/1",
                "city_raw": "Tilburg",
                "gemeente": "Tilburg",
                "discovery_run_id": "20260616T175850Z",
            }
        ],
    )

    result = run_source_coverage_map(
        city="Tilburg",
        province="Noord-Brabant",
        source_master_path=source_master_path,
        platform_fingerprint_path=platform_fingerprint_path,
        property_discovery_run_dir=property_discovery_run_dir,
        output_base_dir=tmp_path / "out",
    )

    assert result.supported_not_in_discovery == 0
    assert result.recommended_next_bottleneck == "improve_existing_source_recovery"


def test_reports_missing_input_without_breaking(tmp_path: Path) -> None:
    source_master_path = tmp_path / "makelaar_sources_master.csv"
    _write_csv(
        source_master_path,
        SOURCE_MASTER_FIELDNAMES,
        [
            {
                "source_id": "unknown-domain__tilburg",
                "office_name": "No Evidence Tilburg",
                "root_domain": "",
                "website": "",
                "gemeente": "Tilburg",
                "province": "Noord-Brabant",
                "aanbod_url": "",
                "legal_status": "missing_website",
                "last_seen_at": "",
                "run_id": "run-1",
            }
        ],
    )

    result = run_source_coverage_map(
        city="Tilburg",
        province="Noord-Brabant",
        source_master_path=source_master_path,
        platform_fingerprint_path=tmp_path / "missing.csv",
        property_discovery_run_dir=tmp_path / "missing",
        output_base_dir=tmp_path / "out",
    )

    row = result.inventory_rows[0]
    assert row["platform_guess"] == "missing_input"
    assert row["operational_status"] == "missing_input"
    assert "missing_input" in row["evidence"]


def test_cli_generates_csv_and_markdown(tmp_path: Path) -> None:
    source_master_path = tmp_path / "makelaar_sources_master.csv"
    platform_fingerprint_path = tmp_path / "platform_fingerprint_results.csv"
    _write_csv(
        source_master_path,
        SOURCE_MASTER_FIELDNAMES,
        [
            {
                "source_id": "alpha.nl__tilburg",
                "office_name": "Alpha Tilburg",
                "root_domain": "alpha.nl",
                "website": "https://alpha.nl",
                "gemeente": "Tilburg",
                "province": "Noord-Brabant",
                "aanbod_url": "https://alpha.nl/aanbod/woningaanbod",
                "legal_status": "allowed_official_source",
                "last_seen_at": "",
                "run_id": "run-1",
            }
        ],
    )
    _write_csv(
        platform_fingerprint_path,
        PLATFORM_FINGERPRINT_FIELDNAMES,
        [
            {
                "source_id": "alpha.nl__tilburg",
                "office_name": "Alpha Tilburg",
                "root_domain": "alpha.nl",
                "website_url": "https://alpha.nl",
                "aanbod_url": "https://alpha.nl/aanbod/woningaanbod",
                "detected_platform": "realworks",
                "confidence": "0.95",
                "evidence": "signal:realworks",
                "fetch_status": "homepage_ok;aanbod_ok",
                "error": "",
            }
        ],
    )
    property_discovery_run_dir = tmp_path / "property_discovery" / "20260616T175850Z"
    _write_csv(property_discovery_run_dir / "property_candidates.csv", PROPERTY_CANDIDATE_FIELDNAMES, [])
    import scripts.run_source_coverage_map as source_coverage_script

    source_coverage_script.DEFAULT_OUTPUT_DIR = tmp_path / "out"

    exit_code = source_coverage_main(
        [
            "--city",
            "Tilburg",
            "--province",
            "Noord-Brabant",
            "--source-master",
            str(source_master_path),
            "--platform-fingerprint",
            str(platform_fingerprint_path),
            "--property-discovery-run-dir",
            str(property_discovery_run_dir),
        ]
    )

    assert exit_code == 0
