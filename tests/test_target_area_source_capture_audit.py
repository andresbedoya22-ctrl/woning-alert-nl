from pathlib import Path
import csv
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.properties.models import CrawlResult, PropertyCandidate, PropertySource
from domek_wonen.properties.source_capture_audit import (
    SOURCE_CAPTURE_AUDIT_FIELDNAMES,
    run_target_area_source_capture_audit,
)


def _source(
    *,
    source_id: str,
    office_name: str,
    root_domain: str,
    gemeente: str,
    aanbod_url: str,
) -> PropertySource:
    return PropertySource(
        source_id=source_id,
        office_name=office_name,
        root_domain=root_domain,
        website=f"https://{root_domain}",
        aanbod_url=aanbod_url,
        gemeente=gemeente,
        province="Noord-Brabant",
        legal_status="allowed_official_source",
        aanbod_url_quality="valid",
        is_active=True,
        detected_platform="realworks",
    )


def _candidate(
    source: PropertySource,
    *,
    property_url: str,
    price_raw: str = "€ 250.000 k.k.",
    city_raw: str = "Tilburg",
    property_type: str = "apartment",
    status_raw: str = "Beschikbaar",
) -> PropertyCandidate:
    return PropertyCandidate(
        source_id=source.source_id,
        source_url=source.aanbod_url,
        root_domain=source.root_domain,
        gemeente=source.gemeente,
        property_url=property_url,
        property_url_classification="property_detail_candidate",
        title="Example Apartment",
        address_raw="Straat 1",
        city_raw=city_raw,
        price_raw=price_raw,
        status_raw=status_raw,
        property_type=property_type,
        extraction_source="realworks_parser",
        detail_extraction_status="succeeded",
        extraction_confidence=0.95,
        address_quality="valid",
    )


def _write_sources_csv(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website,gemeente,province,source_origin,aanbod_url,aanbod_url_quality,aanbod_url_type,confidence_score,score,source_quality_status,source_quality_reason,needs_review,review_reason,legal_status,last_seen_at,last_audited_at,run_id,is_active",
                "kin__tilburg,KIN Tilburg,kinmakelaars.nl,https://kinmakelaars.nl,Tilburg,Noord-Brabant,seed,https://kinmakelaars.nl/aanbod/woningaanbod,valid,listing_index,75,100,valid,,false,,allowed_official_source,20260615T000000Z,,20260615T000000Z,true",
                "rw__waalwijk,Realworks Waalwijk,realworks-waalwijk.nl,https://realworks-waalwijk.nl,Waalwijk,Noord-Brabant,seed,https://realworks-waalwijk.nl/aanbod/woningaanbod,valid,listing_index,75,100,valid,,false,,allowed_official_source,20260615T000000Z,,20260615T000000Z,true",
                "rw__breda,Realworks Breda,realworks-breda.nl,https://realworks-breda.nl,Breda,Noord-Brabant,seed,https://realworks-breda.nl/aanbod/woningaanbod,valid,listing_index,75,100,valid,,false,,allowed_official_source,20260615T000000Z,,20260615T000000Z,true",
            ]
        ),
        encoding="utf-8",
    )


def _write_platform_inventory(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,gemeente,website_url,aanbod_url,detected_platform,confidence_score,detection_reasons,parser_status,recommended_action",
                "kin__tilburg,KIN Tilburg,kinmakelaars.nl,Tilburg,https://kinmakelaars.nl,https://kinmakelaars.nl/aanbod/woningaanbod,realworks,0.95,signal:realworks,supported,use_existing_parser",
                "rw__waalwijk,Realworks Waalwijk,realworks-waalwijk.nl,Waalwijk,https://realworks-waalwijk.nl,https://realworks-waalwijk.nl/aanbod/woningaanbod,realworks,0.95,signal:realworks,supported,use_existing_parser",
                "rw__breda,Realworks Breda,realworks-breda.nl,Breda,https://realworks-breda.nl,https://realworks-breda.nl/aanbod/woningaanbod,realworks,0.95,signal:realworks,supported,use_existing_parser",
            ]
        ),
        encoding="utf-8",
    )


def test_source_capture_audit_generates_expected_csv(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "makelaar_sources_master.csv"
    _write_sources_csv(input_path)
    platform_inventory = tmp_path / "platform_fingerprint" / "target_area" / "20260615T192849Z" / "target_area_platform_fingerprint_inventory.csv"
    _write_platform_inventory(platform_inventory)

    def fake_crawl(**kwargs):
        source = kwargs["source"]
        candidate = _candidate(source, property_url=f"{source.website}/woning/1")
        return CrawlResult(source=source, ok=True, final_url=source.aanbod_url), [candidate]

    monkeypatch.setattr("domek_wonen.properties.source_capture_audit.discovery_engine._crawl_source_in_subprocess", fake_crawl)

    run_id, rows, inventory_path, report_path = run_target_area_source_capture_audit(
        input_path=input_path,
        target_gemeentes=["Tilburg", "Waalwijk"],
        max_sources=10,
        max_properties_per_source=20,
        output_base_dir=tmp_path / "source_capture_audit" / "runs",
        platform_fingerprint_inventory_path=platform_inventory,
    )

    assert run_id
    assert len(rows) == 2
    with inventory_path.open("r", encoding="utf-8", newline="") as handle:
        written = list(csv.DictReader(handle))
    assert list(written[0].keys()) == SOURCE_CAPTURE_AUDIT_FIELDNAMES
    assert report_path.exists()


def test_source_capture_audit_marks_working_source(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "makelaar_sources_master.csv"
    _write_sources_csv(input_path)
    platform_inventory = tmp_path / "target_area_inventory.csv"
    _write_platform_inventory(platform_inventory)

    def fake_crawl(**kwargs):
        source = kwargs["source"]
        candidate = _candidate(source, property_url=f"{source.website}/woning/1")
        return CrawlResult(source=source, ok=True, final_url=source.aanbod_url), [candidate]

    monkeypatch.setattr("domek_wonen.properties.source_capture_audit.discovery_engine._crawl_source_in_subprocess", fake_crawl)

    _run_id, rows, _inventory_path, _report_path = run_target_area_source_capture_audit(
        input_path=input_path,
        target_gemeentes=["Tilburg"],
        root_domain="kinmakelaars.nl",
        output_base_dir=tmp_path / "runs",
        platform_fingerprint_inventory_path=platform_inventory,
    )

    assert len(rows) == 1
    assert rows[0]["recommended_action"] == "working_source"
    assert rows[0]["clean_available"] == "1"


def test_source_capture_audit_marks_timeout_for_supported_source(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "makelaar_sources_master.csv"
    _write_sources_csv(input_path)
    platform_inventory = tmp_path / "target_area_inventory.csv"
    _write_platform_inventory(platform_inventory)

    def fake_crawl(**kwargs):
        source = kwargs["source"]
        return CrawlResult(source=source, ok=False, final_url=source.aanbod_url, error="source timeout after 20s", timed_out=True), []

    monkeypatch.setattr("domek_wonen.properties.source_capture_audit.discovery_engine._crawl_source_in_subprocess", fake_crawl)

    _run_id, rows, _inventory_path, _report_path = run_target_area_source_capture_audit(
        input_path=input_path,
        target_gemeentes=["Tilburg"],
        root_domain="kinmakelaars.nl",
        output_base_dir=tmp_path / "runs",
        platform_fingerprint_inventory_path=platform_inventory,
    )

    assert rows[0]["recommended_action"] == "parser_supported_but_timeout"


def test_source_capture_audit_marks_no_inventory_for_supported_source(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "makelaar_sources_master.csv"
    _write_sources_csv(input_path)
    platform_inventory = tmp_path / "target_area_inventory.csv"
    _write_platform_inventory(platform_inventory)

    def fake_crawl(**kwargs):
        source = kwargs["source"]
        source = _source(
            source_id=source.source_id,
            office_name=source.office_name,
            root_domain=source.root_domain,
            gemeente=source.gemeente,
            aanbod_url="https://kinmakelaars.nl/woningaanbod",
        )
        return CrawlResult(source=source, ok=True, final_url=source.aanbod_url), []

    monkeypatch.setattr("domek_wonen.properties.source_capture_audit.discovery_engine._crawl_source_in_subprocess", fake_crawl)

    _run_id, rows, _inventory_path, _report_path = run_target_area_source_capture_audit(
        input_path=input_path,
        target_gemeentes=["Tilburg"],
        root_domain="kinmakelaars.nl",
        output_base_dir=tmp_path / "runs",
        platform_fingerprint_inventory_path=platform_inventory,
    )

    assert rows[0]["recommended_action"] == "parser_supported_but_no_inventory"


def test_source_capture_audit_marks_no_clean_available_when_inventory_is_dirty(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "makelaar_sources_master.csv"
    _write_sources_csv(input_path)
    platform_inventory = tmp_path / "target_area_inventory.csv"
    _write_platform_inventory(platform_inventory)

    def fake_crawl(**kwargs):
        source = kwargs["source"]
        candidate = _candidate(
            source,
            property_url=f"{source.website}/woning/1",
            price_raw="Prijs op aanvraag",
        )
        return CrawlResult(source=source, ok=True, final_url=source.aanbod_url), [candidate]

    monkeypatch.setattr("domek_wonen.properties.source_capture_audit.discovery_engine._crawl_source_in_subprocess", fake_crawl)

    _run_id, rows, _inventory_path, _report_path = run_target_area_source_capture_audit(
        input_path=input_path,
        target_gemeentes=["Tilburg"],
        root_domain="kinmakelaars.nl",
        output_base_dir=tmp_path / "runs",
        platform_fingerprint_inventory_path=platform_inventory,
    )

    assert rows[0]["properties_found"] == "1"
    assert rows[0]["matching_ready"] == "1"
    assert rows[0]["clean_available"] == "0"
    assert rows[0]["recommended_action"] == "parser_supported_but_no_clean_available"


def test_source_capture_audit_root_domain_filter_works(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "makelaar_sources_master.csv"
    _write_sources_csv(input_path)
    platform_inventory = tmp_path / "target_area_inventory.csv"
    _write_platform_inventory(platform_inventory)

    def fake_crawl(**kwargs):
        source = kwargs["source"]
        candidate = _candidate(source, property_url=f"{source.website}/woning/1")
        return CrawlResult(source=source, ok=True, final_url=source.aanbod_url), [candidate]

    monkeypatch.setattr("domek_wonen.properties.source_capture_audit.discovery_engine._crawl_source_in_subprocess", fake_crawl)

    _run_id, rows, _inventory_path, _report_path = run_target_area_source_capture_audit(
        input_path=input_path,
        target_gemeentes=["Tilburg", "Waalwijk"],
        root_domain="kinmakelaars.nl",
        output_base_dir=tmp_path / "runs",
        platform_fingerprint_inventory_path=platform_inventory,
    )

    assert len(rows) == 1
    assert rows[0]["root_domain"] == "kinmakelaars.nl"
