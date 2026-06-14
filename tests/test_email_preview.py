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


def _write_matching_report(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "# Matching v1 Report",
                "",
                "- Run timestamp: 20260614T190000Z",
                "- Client fixture: cliente_test_brabant_001",
                "- Inventory run used: 20260614T184638Z",
                "- Inventory CSV: data/property_discovery/runs/20260614T184638Z/matching_ready_inventory.csv",
                "- Total clean_available read: 12",
                "- Total after hard filters: 3",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_email_preview_generates_es_nl_and_advisor_report_without_rendering_excluded_rows(tmp_path: Path) -> None:
    run_dir = tmp_path / "matching" / "runs" / "20260614T190000Z"
    results_csv_path = run_dir / "matching_results.csv"
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
                "property_id": "runner_up",
                "address_raw": "Haven 8",
                "city_raw": "Halsteren",
                "price_eur": "420000",
                "bedrooms_count": "4",
                "rooms_count": "5",
                "living_area_m2": "120",
                "energy_label": "B",
                "has_garden": "",
                "has_balcony": "true",
                "score": "88",
                "hard_filter_passed": "true",
                "exclusion_reason": "",
                "warnings": "missing_energy_label",
                "property_url": "https://example.nl/runner-up",
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
            {
                "client_id": "cliente_test_brabant_001",
                "property_id": "over_budget",
                "address_raw": "Straat 9",
                "city_raw": "Breda",
                "price_eur": "530000",
                "bedrooms_count": "4",
                "rooms_count": "5",
                "living_area_m2": "125",
                "energy_label": "A",
                "has_garden": "true",
                "has_balcony": "",
                "score": "",
                "hard_filter_passed": "false",
                "exclusion_reason": "excluded_over_budget",
                "warnings": "",
                "property_url": "https://example.nl/over-budget",
            },
        ],
    )
    _write_matching_report(run_dir / "matching_report.md")

    result = run_email_preview_v1(
        results_csv_path=results_csv_path,
        client_fixture_path=CLIENT_FIXTURE,
        email_preview_runs_dir=tmp_path / "email_previews" / "runs",
    )

    html_es = result.html_es_path.read_text(encoding="utf-8")
    html_nl = result.html_nl_path.read_text(encoding="utf-8")
    report = result.report_path.read_text(encoding="utf-8")

    assert result.top_matches[0]["property_id"] == "winner"
    assert result.html_es_path.name == "email_preview_es.html"
    assert result.html_nl_path.name == "email_preview_nl.html"
    assert result.report_path.name == "advisor_review_report.md"

    assert "Viviendas recomendadas para Cliente test Domek" in html_es
    assert "Woningselectie voor Cliente test Domek" in html_nl
    assert "Vista previa interna. No enviada al cliente." in html_es
    assert "Er worden geen e-mails verzonden." in html_nl
    assert "Por qué aparece esta vivienda" in html_es
    assert "Waarom verschijnt deze woning" in html_nl

    assert "Markt 1" in html_es
    assert "Haven 8" in html_es
    assert "outside_area" not in html_es
    assert "over_budget" not in html_es
    assert "Eindhoven" not in html_es
    assert "Straat 2" not in html_es
    assert "Straat 9" not in html_es
    assert "Resend" not in html_es
    assert "Resend" not in report

    assert "Client used: Cliente test Domek (cliente_test_brabant_001)" in report
    assert "Inventory run used: 20260614T184638Z" in report
    assert "Matching run used: 20260614T190000Z" in report
    assert "Total clean_available: 12" in report
    assert "Total hard_filter_passed: 2" in report
    assert "excluded_outside_target_area: 1" in report
    assert "excluded_missing_bedrooms: 1" in report
    assert "excluded_over_budget: 1" in report
    assert "excluded_bedrooms_below_min: 0" in report
    assert "## Principales warnings" in report
    assert "## Recomendaciones para revisión manual" in report
