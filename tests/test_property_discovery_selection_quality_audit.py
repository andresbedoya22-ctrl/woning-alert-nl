from pathlib import Path
import csv
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.diagnostics.property_discovery_selection_quality_audit import (
    CSV_FIELDNAMES,
    run_property_discovery_selection_quality_audit,
)
from scripts.run_property_discovery_selection_quality_audit import main as audit_main


SOURCE_MASTER_FIELDNAMES = [
    "source_id",
    "office_name",
    "root_domain",
    "website",
    "gemeente",
    "province",
    "source_origin",
    "aanbod_url",
    "aanbod_url_quality",
    "aanbod_url_type",
    "source_quality_status",
    "legal_status",
    "is_active",
]
PLATFORM_FINGERPRINT_FIELDNAMES = [
    "source_id",
    "root_domain",
    "detected_platform",
]
PROPERTY_CANDIDATE_FIELDNAMES = [
    "source_id",
    "root_domain",
    "source_url",
    "property_url",
]
MATCHING_READY_FIELDNAMES = [
    "source_id",
    "source_root_domain",
    "source_aanbod_url",
    "property_url",
    "city_raw",
    "price_eur",
    "status",
    "address_quality",
    "needs_review",
    "needs_review_reason",
]
REJECTED_FIELDNAMES = [
    "source_id",
    "root_domain",
    "source_url",
    "property_url",
    "rejection_reason",
    "needs_review",
    "needs_review_reason",
]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_builds_selection_quality_and_target_area_summary(tmp_path: Path) -> None:
    source_master_path = tmp_path / "makelaar_sources_master.csv"
    override_csv_path = tmp_path / "overrides.csv"
    platform_fingerprint_path = tmp_path / "platform_fingerprint.csv"
    current_run_dir = tmp_path / "property_discovery" / "runs" / "20260616T190359Z"
    previous_run_dir = tmp_path / "property_discovery" / "runs" / "20260615T204218Z"

    _write_csv(
        source_master_path,
        SOURCE_MASTER_FIELDNAMES,
        [
            {
                "source_id": "allroundmakelaardij.nl__tilburg",
                "office_name": "Allround Makelaardij",
                "root_domain": "allroundmakelaardij.nl",
                "website": "https://www.allroundmakelaardij.nl",
                "gemeente": "Tilburg",
                "province": "Noord-Brabant",
                "source_origin": "property_discovery_supported_batch_v1",
                "aanbod_url": "https://www.allroundmakelaardij.nl/woningen/",
                "aanbod_url_quality": "valid",
                "aanbod_url_type": "listing_index",
                "source_quality_status": "valid",
                "legal_status": "allowed_official_source",
                "is_active": "true",
            },
            {
                "source_id": "cvda.nl__tilburg",
                "office_name": "CVDA",
                "root_domain": "cvda.nl",
                "website": "https://www.cvda.nl",
                "gemeente": "Tilburg",
                "province": "Noord-Brabant",
                "source_origin": "property_discovery_supported_batch_v1",
                "aanbod_url": "https://www.cvda.nl/aanbod/woningaanbod/",
                "aanbod_url_quality": "valid",
                "aanbod_url_type": "listing_index",
                "source_quality_status": "valid",
                "legal_status": "allowed_official_source",
                "is_active": "true",
            },
            {
                "source_id": "kinmakelaars.nl__tilburg",
                "office_name": "KIN",
                "root_domain": "kinmakelaars.nl",
                "website": "https://www.kinmakelaars.nl",
                "gemeente": "Tilburg",
                "province": "Noord-Brabant",
                "source_origin": "seed",
                "aanbod_url": "https://www.kinmakelaars.nl/aanbod/wonen/te-koop",
                "aanbod_url_quality": "valid",
                "aanbod_url_type": "listing_index",
                "source_quality_status": "valid",
                "legal_status": "allowed_official_source",
                "is_active": "true",
            },
            {
                "source_id": "missing.nl__tilburg",
                "office_name": "Missing Source",
                "root_domain": "missing.nl",
                "website": "https://www.missing.nl",
                "gemeente": "Tilburg",
                "province": "Noord-Brabant",
                "source_origin": "seed",
                "aanbod_url": "",
                "aanbod_url_quality": "missing",
                "aanbod_url_type": "missing",
                "source_quality_status": "missing",
                "legal_status": "allowed_official_source",
                "is_active": "true",
            },
        ],
    )
    _write_csv(
        override_csv_path,
        SOURCE_MASTER_FIELDNAMES,
        [
            {
                "source_id": "allroundmakelaardij.nl__tilburg",
                "office_name": "Allround Makelaardij",
                "root_domain": "allroundmakelaardij.nl",
                "website": "https://www.allroundmakelaardij.nl",
                "gemeente": "Tilburg",
                "province": "Noord-Brabant",
                "source_origin": "property_discovery_supported_batch_v1",
                "aanbod_url": "https://www.allroundmakelaardij.nl/woningen/",
                "aanbod_url_quality": "valid",
                "aanbod_url_type": "listing_index",
                "source_quality_status": "valid",
                "legal_status": "allowed_official_source",
                "is_active": "true",
            },
            {
                "source_id": "cvda.nl__tilburg",
                "office_name": "CVDA",
                "root_domain": "cvda.nl",
                "website": "https://www.cvda.nl",
                "gemeente": "Tilburg",
                "province": "Noord-Brabant",
                "source_origin": "property_discovery_supported_batch_v1",
                "aanbod_url": "https://www.cvda.nl/aanbod/woningaanbod/",
                "aanbod_url_quality": "valid",
                "aanbod_url_type": "listing_index",
                "source_quality_status": "valid",
                "legal_status": "allowed_official_source",
                "is_active": "true",
            },
        ],
    )
    _write_csv(
        platform_fingerprint_path,
        PLATFORM_FINGERPRINT_FIELDNAMES,
        [
            {"source_id": "allroundmakelaardij.nl__tilburg", "root_domain": "allroundmakelaardij.nl", "detected_platform": "realworks"},
            {"source_id": "cvda.nl__tilburg", "root_domain": "cvda.nl", "detected_platform": "realworks"},
            {"source_id": "kinmakelaars.nl__tilburg", "root_domain": "kinmakelaars.nl", "detected_platform": "realworks"},
            {"source_id": "missing.nl__tilburg", "root_domain": "missing.nl", "detected_platform": "custom"},
        ],
    )
    _write_csv(
        current_run_dir / "property_candidates.csv",
        PROPERTY_CANDIDATE_FIELDNAMES,
        [
            {"source_id": "allroundmakelaardij.nl__tilburg", "root_domain": "allroundmakelaardij.nl", "source_url": "", "property_url": "https://www.allroundmakelaardij.nl/object/1"},
            {"source_id": "allroundmakelaardij.nl__tilburg", "root_domain": "allroundmakelaardij.nl", "source_url": "", "property_url": "https://www.allroundmakelaardij.nl/object/2"},
            {"source_id": "allroundmakelaardij.nl__tilburg", "root_domain": "allroundmakelaardij.nl", "source_url": "", "property_url": "https://www.allroundmakelaardij.nl/object/3"},
            {"source_id": "cvda.nl__tilburg", "root_domain": "cvda.nl", "source_url": "", "property_url": "https://www.cvda.nl/object/1"},
            {"source_id": "cvda.nl__tilburg", "root_domain": "cvda.nl", "source_url": "", "property_url": "https://www.cvda.nl/object/2"},
        ],
    )
    _write_csv(
        current_run_dir / "matching_ready_inventory.csv",
        MATCHING_READY_FIELDNAMES,
        [
            {
                "source_id": "allroundmakelaardij.nl__tilburg",
                "source_root_domain": "allroundmakelaardij.nl",
                "source_aanbod_url": "",
                "property_url": "https://www.allroundmakelaardij.nl/object/1",
                "city_raw": "Tilburg",
                "price_eur": "350000",
                "status": "unknown",
                "address_quality": "valid",
                "needs_review": "true",
                "needs_review_reason": "unknown_status",
            },
            {
                "source_id": "allroundmakelaardij.nl__tilburg",
                "source_root_domain": "allroundmakelaardij.nl",
                "source_aanbod_url": "",
                "property_url": "https://www.allroundmakelaardij.nl/object/2",
                "city_raw": "5041 GS Tilburg",
                "price_eur": "1200",
                "status": "unknown",
                "address_quality": "valid",
                "needs_review": "true",
                "needs_review_reason": "invalid_price",
            },
            {
                "source_id": "cvda.nl__tilburg",
                "source_root_domain": "cvda.nl",
                "source_aanbod_url": "",
                "property_url": "https://www.cvda.nl/object/1",
                "city_raw": "Tilburg",
                "price_eur": "225000",
                "status": "beschikbaar",
                "address_quality": "valid",
                "needs_review": "false",
                "needs_review_reason": "",
            },
            {
                "source_id": "cvda.nl__tilburg",
                "source_root_domain": "cvda.nl",
                "source_aanbod_url": "",
                "property_url": "https://www.cvda.nl/object/2",
                "city_raw": "Waalwijk",
                "price_eur": "245000",
                "status": "beschikbaar",
                "address_quality": "valid",
                "needs_review": "false",
                "needs_review_reason": "",
            },
        ],
    )
    _write_csv(
        current_run_dir / "rejected_property_candidates.csv",
        REJECTED_FIELDNAMES,
        [
            {
                "source_id": "allroundmakelaardij.nl__tilburg",
                "root_domain": "allroundmakelaardij.nl",
                "source_url": "",
                "property_url": "https://www.allroundmakelaardij.nl/rejected",
                "rejection_reason": "invalid_address_raw",
                "needs_review": "true",
                "needs_review_reason": "invalid_address_raw",
            }
        ],
    )
    _write_csv(
        previous_run_dir / "matching_ready_inventory.csv",
        MATCHING_READY_FIELDNAMES,
        [
            {
                "source_id": "kinmakelaars.nl__tilburg",
                "source_root_domain": "kinmakelaars.nl",
                "source_aanbod_url": "",
                "property_url": "https://www.kinmakelaars.nl/object/1",
                "city_raw": "Tilburg",
                "price_eur": "220000",
                "status": "beschikbaar",
                "address_quality": "valid",
                "needs_review": "false",
                "needs_review_reason": "",
            }
        ],
    )

    result = run_property_discovery_selection_quality_audit(
        city="Tilburg",
        province="noord-brabant",
        property_discovery_run_dir=current_run_dir,
        source_master_path=source_master_path,
        override_csv_path=override_csv_path,
        platform_fingerprint_path=platform_fingerprint_path,
        property_discovery_runs_dir=tmp_path / "property_discovery" / "runs",
        output_base_dir=tmp_path / "out",
    )

    assert result.report_path.exists()
    assert result.inventory_path.exists()
    assert result.recommended_decision == "mixed"

    with result.inventory_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert list(rows[0].keys()) == CSV_FIELDNAMES
    row_by_domain = {row["source_domain"]: row for row in rows}

    assert row_by_domain["kinmakelaars.nl"]["included_in_current_run"] == "false"
    assert row_by_domain["kinmakelaars.nl"]["excluded_by_max_sources_or_priority"] == "true"
    assert row_by_domain["kinmakelaars.nl"]["included_in_baseline_or_previous_validated_run"] == "true"
    assert row_by_domain["kinmakelaars.nl"]["kin_current_run_status"] == "not_included"

    assert row_by_domain["allroundmakelaardij.nl"]["recommended_action"] == "fix_status_extraction"
    assert row_by_domain["allroundmakelaardij.nl"]["clean_available"] == "0"
    assert row_by_domain["allroundmakelaardij.nl"]["invalid_address_count"] == "1"

    assert row_by_domain["cvda.nl"]["recommended_action"] == "not_enough_data"
    assert row_by_domain["cvda.nl"]["target_city_clean_available"] == "1"
    assert row_by_domain["cvda.nl"]["outside_city_clean_available"] == "1"
    assert row_by_domain["cvda.nl"]["can_support_city_specific_search"] == "true"
    assert row_by_domain["cvda.nl"]["filtering_risk"] == "low"

    assert row_by_domain["missing.nl"]["excluded_by_missing_aanbod_url"] == "true"

    report_text = result.report_path.read_text(encoding="utf-8")
    assert "KIN current_run_status: not_included" in report_text
    assert "recommended_decision: mixed" in report_text


def test_cli_generates_outputs_for_requested_domains(tmp_path: Path) -> None:
    source_master_path = tmp_path / "makelaar_sources_master.csv"
    platform_fingerprint_path = tmp_path / "platform_fingerprint.csv"
    run_dir = tmp_path / "property_discovery" / "runs" / "20260616T190359Z"

    _write_csv(
        source_master_path,
        SOURCE_MASTER_FIELDNAMES,
        [
            {
                "source_id": "cvda.nl__tilburg",
                "office_name": "CVDA",
                "root_domain": "cvda.nl",
                "website": "https://www.cvda.nl",
                "gemeente": "Tilburg",
                "province": "Noord-Brabant",
                "source_origin": "property_discovery_supported_batch_v1",
                "aanbod_url": "https://www.cvda.nl/aanbod/woningaanbod/",
                "aanbod_url_quality": "valid",
                "aanbod_url_type": "listing_index",
                "source_quality_status": "valid",
                "legal_status": "allowed_official_source",
                "is_active": "true",
            }
        ],
    )
    _write_csv(
        platform_fingerprint_path,
        PLATFORM_FINGERPRINT_FIELDNAMES,
        [
            {"source_id": "cvda.nl__tilburg", "root_domain": "cvda.nl", "detected_platform": "realworks"}
        ],
    )
    _write_csv(run_dir / "property_candidates.csv", PROPERTY_CANDIDATE_FIELDNAMES, [])
    _write_csv(run_dir / "matching_ready_inventory.csv", MATCHING_READY_FIELDNAMES, [])
    _write_csv(run_dir / "rejected_property_candidates.csv", REJECTED_FIELDNAMES, [])

    exit_code = audit_main(
        [
            "--city",
            "Tilburg",
            "--province",
            "Noord-Brabant",
            "--property-discovery-run-dir",
            str(run_dir),
            "--source-domain",
            "cvda.nl",
            "--source-master",
            str(source_master_path),
            "--platform-fingerprint",
            str(platform_fingerprint_path),
            "--output-base-dir",
            str(tmp_path / "out"),
        ]
    )

    assert exit_code == 0
    output_dirs = list((tmp_path / "out").iterdir())
    assert len(output_dirs) == 1
    assert (output_dirs[0] / "selection_quality_report.md").exists()
    assert (output_dirs[0] / "selection_quality_inventory.csv").exists()
