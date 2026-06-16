from pathlib import Path
import csv
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.diagnostics.source_recovery_tracker import normalize_address, run_source_recovery_tracker


BENCHMARK_FIELDNAMES = [
    "expected_id",
    "address",
    "city",
    "price_eur",
    "property_type",
    "rooms_count",
    "living_area_m2",
    "energy_label",
    "status_expected",
    "source_note",
]

CANDIDATE_FIELDNAMES = [
    "source_id",
    "root_domain",
    "source_url",
    "property_url",
    "candidate_type",
    "link_text",
    "extraction_method",
    "excluded_reason",
    "is_property_like",
    "property_url_classification",
    "title",
    "address_raw",
    "city_raw",
    "gemeente",
    "price_raw",
    "status_raw",
    "living_area_raw",
    "plot_area_raw",
    "rooms_raw",
    "rooms_count",
    "bedrooms_count",
    "living_area_m2",
    "property_type",
    "energy_label",
    "has_garden",
    "has_balcony",
    "image_url",
    "extraction_source",
    "detail_extraction_status",
    "detail_error",
    "extraction_confidence",
    "address_quality",
    "needs_review",
    "needs_review_reason",
    "review_reason",
]

REJECTED_FIELDNAMES = CANDIDATE_FIELDNAMES + ["rejection_reason"]

MATCHING_READY_FIELDNAMES = [
    "property_id",
    "source_id",
    "source_root_domain",
    "source_aanbod_url",
    "property_url",
    "title",
    "address_raw",
    "city_raw",
    "gemeente",
    "price_raw",
    "price_eur",
    "status",
    "status_raw",
    "living_area_raw",
    "plot_area_raw",
    "rooms_raw",
    "rooms_count",
    "bedrooms_count",
    "living_area_m2",
    "property_type",
    "energy_label",
    "has_garden",
    "has_balcony",
    "image_url",
    "extraction_source",
    "detail_extraction_status",
    "detail_error",
    "first_seen_at",
    "last_seen_at",
    "discovery_run_id",
    "extraction_confidence",
    "address_quality",
    "needs_review",
    "needs_review_reason",
    "review_reason",
]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _candidate_row(**overrides: str) -> dict[str, str]:
    row = {field: "" for field in CANDIDATE_FIELDNAMES}
    row.update(
        {
            "source_id": "kinmakelaars.nl__tilburg",
            "root_domain": "kinmakelaars.nl",
            "source_url": "https://www.kinmakelaars.nl/aanbod/wonen/te-koop",
            "property_url": "https://www.kinmakelaars.nl/aanbod/wonen/tilburg/example-1/object",
            "candidate_type": "platform_parser_detail_url",
            "is_property_like": "true",
            "property_url_classification": "property_detail_candidate",
            "title": "Example",
            "address_raw": "Example 1",
            "city_raw": "Tilburg",
            "gemeente": "Tilburg",
            "price_raw": "€ 200.000 k.k.",
            "status_raw": "Nieuw",
            "living_area_raw": "40 m²",
            "rooms_raw": "2 kamers",
            "rooms_count": "2",
            "bedrooms_count": "1",
            "living_area_m2": "40",
            "property_type": "apartment",
            "extraction_source": "realworks_parser",
            "detail_extraction_status": "succeeded",
            "extraction_confidence": "0.95",
            "address_quality": "valid",
            "needs_review": "false",
        }
    )
    row.update(overrides)
    return row


def _rejected_row(**overrides: str) -> dict[str, str]:
    row = {field: "" for field in REJECTED_FIELDNAMES}
    row.update(_candidate_row())
    row["rejection_reason"] = "listing-like path without property slug"
    row.update(overrides)
    return row


def _matching_ready_row(property_id: str, **overrides: str) -> dict[str, str]:
    row = {field: "" for field in MATCHING_READY_FIELDNAMES}
    row.update(
        {
            "property_id": property_id,
            "source_id": "kinmakelaars.nl__tilburg",
            "source_root_domain": "kinmakelaars.nl",
            "source_aanbod_url": "https://www.kinmakelaars.nl/aanbod/wonen/te-koop",
            "property_url": f"https://www.kinmakelaars.nl/aanbod/wonen/tilburg/{property_id}",
            "title": property_id,
            "address_raw": property_id,
            "city_raw": "Tilburg",
            "gemeente": "Tilburg",
            "price_raw": "€ 200.000 k.k.",
            "price_eur": "200000",
            "status": "beschikbaar",
            "status_raw": "Nieuw",
            "living_area_raw": "40 m²",
            "rooms_raw": "2 kamers",
            "rooms_count": "2",
            "bedrooms_count": "1",
            "living_area_m2": "40",
            "property_type": "apartment",
            "extraction_source": "realworks_parser",
            "detail_extraction_status": "succeeded",
            "discovery_run_id": "20260616T165926Z",
            "extraction_confidence": "0.95",
            "address_quality": "valid",
            "needs_review": "false",
        }
    )
    row.update(overrides)
    return row


def test_normalize_address_matches_hyphenated_variant() -> None:
    assert normalize_address("Roemerhof 16", "Tilburg") == normalize_address("roemerhof-16", "Tilburg")


def test_normalize_address_tolerates_city_suffix() -> None:
    assert normalize_address("Roemerhof 16 Tilburg", "Tilburg") == "roemerhof 16"


def test_tracker_finds_trouwlaan_285_clean_in_matching_ready(tmp_path: Path) -> None:
    benchmark_csv = tmp_path / "benchmark.csv"
    candidates_csv = tmp_path / "property_candidates.csv"
    rejected_csv = tmp_path / "property_rejected.csv"
    matching_ready_csv = tmp_path / "matching_ready_inventory.csv"
    _write_csv(
        benchmark_csv,
        BENCHMARK_FIELDNAMES,
        [
            {
                "expected_id": "kin_001",
                "address": "Trouwlaan 285",
                "city": "Tilburg",
                "price_eur": "220000",
                "property_type": "apartment",
                "rooms_count": "2",
                "living_area_m2": "38",
                "energy_label": "",
                "status_expected": "beschikbaar",
                "source_note": "test",
            }
        ],
    )
    _write_csv(
        candidates_csv,
        CANDIDATE_FIELDNAMES,
        [
            _candidate_row(
                property_url="https://kinmakelaars.nl/trouwlaan-285",
                title="Trouwlaan 285",
                address_raw="Trouwlaan 285",
                price_raw="€ 220.000 k.k.",
                living_area_raw="38 m²",
                rooms_raw="2 kamers",
                rooms_count="2",
                living_area_m2="38",
            )
        ],
    )
    _write_csv(rejected_csv, REJECTED_FIELDNAMES, [])
    _write_csv(
        matching_ready_csv,
        MATCHING_READY_FIELDNAMES,
        [
            _matching_ready_row(
                "Trouwlaan 285",
                property_url="https://kinmakelaars.nl/trouwlaan-285",
                address_raw="Trouwlaan 285",
                price_raw="€ 220.000 k.k.",
                price_eur="220000",
                living_area_raw="38 m²",
                rooms_raw="2 kamers",
                rooms_count="2",
                living_area_m2="38",
            )
        ],
    )

    result = run_source_recovery_tracker(
        benchmark_csv_path=benchmark_csv,
        candidates_csv_path=candidates_csv,
        rejected_csv_path=rejected_csv,
        matching_ready_csv_path=matching_ready_csv,
        output_base_dir=tmp_path / "out",
    )

    with result.inventory_output_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows[0]["found_in_candidates"] == "true"
    assert rows[0]["found_in_matching_ready"] == "true"
    assert rows[0]["found_clean_available"] == "true"
    assert rows[0]["final_recovery_stage"] == "found_clean_included"


def test_tracker_marks_not_seen_in_candidates_when_expected_absent(tmp_path: Path) -> None:
    benchmark_csv = tmp_path / "benchmark.csv"
    candidates_csv = tmp_path / "property_candidates.csv"
    rejected_csv = tmp_path / "property_rejected.csv"
    matching_ready_csv = tmp_path / "matching_ready_inventory.csv"
    _write_csv(
        benchmark_csv,
        BENCHMARK_FIELDNAMES,
        [
            {
                "expected_id": "kin_002",
                "address": "Roemerhof 16",
                "city": "Tilburg",
                "price_eur": "180000",
                "property_type": "apartment",
                "rooms_count": "2",
                "living_area_m2": "23",
                "energy_label": "A",
                "status_expected": "beschikbaar",
                "source_note": "test",
            }
        ],
    )
    _write_csv(candidates_csv, CANDIDATE_FIELDNAMES, [])
    _write_csv(rejected_csv, REJECTED_FIELDNAMES, [])
    _write_csv(matching_ready_csv, MATCHING_READY_FIELDNAMES, [])

    result = run_source_recovery_tracker(
        benchmark_csv_path=benchmark_csv,
        candidates_csv_path=candidates_csv,
        rejected_csv_path=rejected_csv,
        matching_ready_csv_path=matching_ready_csv,
        output_base_dir=tmp_path / "out",
    )

    with result.inventory_output_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows[0]["found_in_candidates"] == "false"
    assert rows[0]["final_recovery_stage"] == "not_seen_in_candidates"


def test_tracker_marks_candidate_seen_but_rejected_for_roemerhof_16(tmp_path: Path) -> None:
    benchmark_csv = tmp_path / "benchmark.csv"
    candidates_csv = tmp_path / "property_candidates.csv"
    rejected_csv = tmp_path / "property_rejected.csv"
    matching_ready_csv = tmp_path / "matching_ready_inventory.csv"
    _write_csv(
        benchmark_csv,
        BENCHMARK_FIELDNAMES,
        [
            {
                "expected_id": "kin_003",
                "address": "Roemerhof 16",
                "city": "Tilburg",
                "price_eur": "180000",
                "property_type": "apartment",
                "rooms_count": "2",
                "living_area_m2": "23",
                "energy_label": "A",
                "status_expected": "beschikbaar",
                "source_note": "test",
            }
        ],
    )
    _write_csv(
        candidates_csv,
        CANDIDATE_FIELDNAMES,
        [
            _candidate_row(
                property_url="https://kinmakelaars.nl/roemerhof-16",
                title="Roemerhof 16",
                address_raw="Roemerhof 16 Tilburg",
                price_raw="€ 180.000 k.k.",
                living_area_raw="23 m²",
                rooms_raw="2 kamers",
                rooms_count="2",
                living_area_m2="23",
            )
        ],
    )
    _write_csv(
        rejected_csv,
        REJECTED_FIELDNAMES,
        [
            _rejected_row(
                property_url="https://kinmakelaars.nl/roemerhof-16",
                title="Roemerhof 16",
                address_raw="roemerhof-16",
                price_raw="€ 180.000 k.k.",
                living_area_raw="23 m²",
                rooms_raw="2 kamers",
                rooms_count="2",
                living_area_m2="23",
                property_type="maisonette",
                excluded_reason="listing-like path without property slug",
                rejection_reason="listing-like path without property slug",
            )
        ],
    )
    _write_csv(matching_ready_csv, MATCHING_READY_FIELDNAMES, [])

    result = run_source_recovery_tracker(
        benchmark_csv_path=benchmark_csv,
        candidates_csv_path=candidates_csv,
        rejected_csv_path=rejected_csv,
        matching_ready_csv_path=matching_ready_csv,
        output_base_dir=tmp_path / "out",
    )

    with result.inventory_output_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows[0]["found_in_candidates"] == "true"
    assert rows[0]["found_in_rejected"] == "true"
    assert rows[0]["found_in_matching_ready"] == "false"
    assert rows[0]["final_recovery_stage"] == "candidate_seen_but_rejected"
    assert "listing-like path without property slug" in rows[0]["final_loss_reason"]


def test_report_includes_counts_by_candidates_rejected_matching_ready(tmp_path: Path) -> None:
    benchmark_csv = tmp_path / "benchmark.csv"
    candidates_csv = tmp_path / "property_candidates.csv"
    rejected_csv = tmp_path / "property_rejected.csv"
    matching_ready_csv = tmp_path / "matching_ready_inventory.csv"
    _write_csv(
        benchmark_csv,
        BENCHMARK_FIELDNAMES,
        [
            {
                "expected_id": "kin_004",
                "address": "Trouwlaan 285",
                "city": "Tilburg",
                "price_eur": "220000",
                "property_type": "apartment",
                "rooms_count": "2",
                "living_area_m2": "38",
                "energy_label": "",
                "status_expected": "beschikbaar",
                "source_note": "test",
            },
            {
                "expected_id": "kin_005",
                "address": "Roemerhof 16",
                "city": "Tilburg",
                "price_eur": "180000",
                "property_type": "apartment",
                "rooms_count": "2",
                "living_area_m2": "23",
                "energy_label": "A",
                "status_expected": "beschikbaar",
                "source_note": "test",
            },
        ],
    )
    _write_csv(
        candidates_csv,
        CANDIDATE_FIELDNAMES,
        [
            _candidate_row(
                property_url="https://kinmakelaars.nl/trouwlaan-285",
                title="Trouwlaan 285",
                address_raw="Trouwlaan 285 Tilburg",
                price_raw="€ 220.000 k.k.",
                living_area_raw="38 m²",
                rooms_raw="2 kamers",
                rooms_count="2",
                living_area_m2="38",
            )
        ],
    )
    _write_csv(rejected_csv, REJECTED_FIELDNAMES, [])
    _write_csv(
        matching_ready_csv,
        MATCHING_READY_FIELDNAMES,
        [
            _matching_ready_row(
                "Trouwlaan 285",
                property_url="https://kinmakelaars.nl/trouwlaan-285",
                address_raw="Trouwlaan 285 Tilburg",
                price_raw="€ 220.000 k.k.",
                price_eur="220000",
                living_area_raw="38 m²",
                rooms_raw="2 kamers",
                rooms_count="2",
                living_area_m2="38",
            )
        ],
    )

    result = run_source_recovery_tracker(
        benchmark_csv_path=benchmark_csv,
        candidates_csv_path=candidates_csv,
        rejected_csv_path=rejected_csv,
        matching_ready_csv_path=matching_ready_csv,
        output_base_dir=tmp_path / "out",
    )

    report = result.report_path.read_text(encoding="utf-8")

    assert "found_in_candidates_count: 1" in report
    assert "found_in_rejected_count: 0" in report
    assert "found_in_matching_ready_count: 1" in report
    assert "gross_recovery_pct: 50.0" in report
    assert "| Roemerhof 16 | not_seen_in_candidates | false | false | false | false | false | missing_address_city_match_in_candidates |" in report
