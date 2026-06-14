from pathlib import Path
import csv
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.matching.email_preview import run_email_preview_v1


CLIENT_FIXTURE = Path("fixtures/matching/clients/client_test_brabant_001.json")
FIELDNAMES = [
    "client_id",
    "property_id",
    "address_raw",
    "city_raw",
    "price_eur",
    "bedrooms_count",
    "rooms_count",
    "living_area_m2",
    "energy_label",
    "has_garden",
    "has_balcony",
    "score",
    "hard_filter_passed",
    "exclusion_reason",
    "warnings",
    "property_url",
]


def _write_results_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def test_email_preview_renders_top_matches_and_reports_hard_filter_exclusions(tmp_path: Path) -> None:
    results_csv_path = tmp_path / "matching" / "runs" / "20260614T190000Z" / "matching_results.csv"
    _write_results_csv(
        results_csv_path,
        [
            {
                "client_id": "cliente_test_brabant_001",
                "property_id": "winner",
                "address_raw": "Markt 1",
                "city_raw": "Breda",
                "price_eur": "450000",
                "bedrooms_count": "3",
                "rooms_count": "5",
                "living_area_m2": "102",
                "energy_label": "A",
                "has_garden": "true",
                "has_balcony": "",
                "score": "92",
                "hard_filter_passed": "true",
                "exclusion_reason": "",
                "warnings": "missing_garden_or_balcony",
                "property_url": "https://example.nl/winner",
            },
            {
                "client_id": "cliente_test_brabant_001",
                "property_id": "missing_bedrooms",
                "address_raw": "Straat 2",
                "city_raw": "Breda",
                "price_eur": "440000",
                "bedrooms_count": "",
                "rooms_count": "4",
                "living_area_m2": "95",
                "energy_label": "B",
                "has_garden": "",
                "has_balcony": "",
                "score": "",
                "hard_filter_passed": "false",
                "exclusion_reason": "excluded_missing_bedrooms",
                "warnings": "",
                "property_url": "https://example.nl/missing-bedrooms",
            },
            {
                "client_id": "cliente_test_brabant_001",
                "property_id": "outside_area",
                "address_raw": "Straat 3",
                "city_raw": "Eindhoven",
                "price_eur": "430000",
                "bedrooms_count": "4",
                "rooms_count": "5",
                "living_area_m2": "110",
                "energy_label": "A",
                "has_garden": "true",
                "has_balcony": "",
                "score": "",
                "hard_filter_passed": "false",
                "exclusion_reason": "excluded_outside_target_area",
                "warnings": "",
                "property_url": "https://example.nl/outside-area",
            },
        ],
    )

    result = run_email_preview_v1(
        results_csv_path=results_csv_path,
        client_fixture_path=CLIENT_FIXTURE,
        email_preview_runs_dir=tmp_path / "email_previews" / "runs",
    )

    html = result.html_path.read_text(encoding="utf-8")
    report = result.report_path.read_text(encoding="utf-8")

    assert result.top_matches[0]["property_id"] == "winner"
    assert "Viviendas recomendadas para Cliente test Domek" in html
    assert "Vista previa interna. No enviada al cliente." in html
    assert "Markt 1" in html
    assert "excluded_missing_bedrooms" not in html
    assert "outside_area" not in html
    assert "Eindhoven" not in html
    assert "Email sending: disabled" in report
    assert "Excluded outside target area: 1" in report
    assert "Excluded missing bedrooms: 1" in report
    assert "winner" in report
