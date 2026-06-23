from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.sources.evidence_enrichment import (
    build_enriched_legacy_source_report,
    enrich_source_records_with_evidence,
    load_platform_evidence,
)
from domek_wonen.sources.legacy_source_adapter import load_legacy_source_records
from domek_wonen.sources.source_intelligence_models import SourceIntelligenceRecord


EVIDENCE_FIXTURE = Path("tests/fixtures/sources/platform_evidence_seed.csv")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_source_master(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website,gemeente,province,aanbod_url,aanbod_url_quality,legal_status,is_active",
                "realworks__tilburg,Realworks Enrich,realworks-enrich.test,https://realworks-enrich.test,Tilburg,Noord-Brabant,https://realworks-enrich.test/aanbod,valid,allowed_official_source,true",
                "ogonline__tilburg,OGonline Enrich,ogonline-enrich.test,https://ogonline-enrich.test,Tilburg,Noord-Brabant,https://ogonline-enrich.test/woningen,valid,allowed_official_source,true",
                "kolibri__tilburg,Kolibri Enrich,kolibri-enrich.test,https://kolibri-enrich.test,Tilburg,Noord-Brabant,https://kolibri-enrich.test/aanbod,valid,allowed_official_source,true",
                "wordpress__tilburg,WordPress Enrich,wordpress-enrich.test,https://wordpress-enrich.test,Tilburg,Noord-Brabant,https://wordpress-enrich.test/woningaanbod,valid,allowed_official_source,true",
                "static__tilburg,Static Enrich,static-enrich.test,https://static-enrich.test,Tilburg,Noord-Brabant,https://static-enrich.test/koopwoningen,valid,allowed_official_source,true",
                "jsonld__tilburg,JsonLd Enrich,jsonld-enrich.test,https://jsonld-enrich.test,Tilburg,Noord-Brabant,https://jsonld-enrich.test/aanbod,valid,allowed_official_source,true",
                "funda__tilburg,Funda Wrapper,funda-wrapper-enrich.test,https://funda-wrapper-enrich.test,Tilburg,Noord-Brabant,,missing,needs_manual_review,false",
                "unknown__tilburg,Unknown Enrich,unknown-enrich.test,https://unknown-enrich.test,Tilburg,Noord-Brabant,,missing,missing,false",
            ]
        ),
        encoding="utf-8",
    )


def test_load_platform_evidence_loads_csv() -> None:
    evidence = load_platform_evidence(EVIDENCE_FIXTURE)

    assert "realworks-enrich.test" in evidence
    assert evidence["realworks-enrich.test"]["detected_platform"] == "realworks"


def test_join_by_source_domain_works() -> None:
    record = SourceIntelligenceRecord(source_domain="realworks-enrich.test", access_status="allowed")

    enriched = enrich_source_records_with_evidence([record], load_platform_evidence(EVIDENCE_FIXTURE))[0]

    assert enriched.detected_platform == "realworks"
    assert enriched.delivery_mode == "realworks_public"


def test_join_by_root_domain_works(tmp_path: Path) -> None:
    evidence_path = tmp_path / "root-domain-evidence.csv"
    _write_csv(
        evidence_path,
        [{"root_domain": "root-join.test", "detected_platform": "ogonline", "confidence": "0.9"}],
    )
    record = SourceIntelligenceRecord(source_domain="root-join.test", access_status="allowed")

    enriched = enrich_source_records_with_evidence([record], load_platform_evidence(evidence_path))[0]

    assert enriched.delivery_mode == "ogonline_xhr"


def test_join_by_homepage_url_domain_works(tmp_path: Path) -> None:
    evidence_path = tmp_path / "homepage-evidence.csv"
    _write_csv(
        evidence_path,
        [{"homepage_url": "https://www.homepage-join.test", "detected_platform": "kolibri", "confidence": "0.9"}],
    )
    record = SourceIntelligenceRecord(homepage_url="https://homepage-join.test", access_status="allowed")

    enriched = enrich_source_records_with_evidence([record], load_platform_evidence(evidence_path))[0]

    assert enriched.detected_platform == "kolibri"
    assert enriched.delivery_mode == "kolibri_public"


def test_detected_platform_transfers() -> None:
    record = SourceIntelligenceRecord(source_domain="wordpress-enrich.test", access_status="allowed")

    enriched = enrich_source_records_with_evidence([record], load_platform_evidence(EVIDENCE_FIXTURE))[0]

    assert enriched.detected_platform == "wordpress"
    assert enriched.has_wp_json is True


def test_booleans_true_win_over_false(tmp_path: Path) -> None:
    evidence_path = tmp_path / "boolean-evidence.csv"
    _write_csv(
        evidence_path,
        [
            {"source_domain": "boolean-merge.test", "has_json_ld": "true", "confidence": "0.4"},
            {"source_domain": "boolean-merge.test", "has_json_ld": "false", "confidence": "0.9"},
        ],
    )

    evidence = load_platform_evidence(evidence_path)

    assert evidence["boolean-merge.test"]["has_json_ld"] is True


def test_evidence_text_is_preserved_and_concatenated(tmp_path: Path) -> None:
    evidence_path = tmp_path / "text-evidence.csv"
    _write_csv(
        evidence_path,
        [
            {"source_domain": "text-merge.test", "evidence": "first", "confidence": "0.4"},
            {"source_domain": "text-merge.test", "evidence": "second", "confidence": "0.5"},
        ],
    )
    record = SourceIntelligenceRecord(source_domain="text-merge.test", evidence="base")

    enriched = enrich_source_records_with_evidence([record], load_platform_evidence(evidence_path))[0]

    assert enriched.evidence == "base | first | second"


def test_stronger_platform_evidence_is_not_overwritten_by_unknown() -> None:
    record = SourceIntelligenceRecord(
        source_domain="stronger-enrich.test",
        detected_platform="realworks",
        delivery_mode_confidence=0.9,
        access_status="allowed",
    )

    enriched = enrich_source_records_with_evidence([record], load_platform_evidence(EVIDENCE_FIXTURE))[0]

    assert enriched.detected_platform == "realworks"
    assert enriched.delivery_mode == "realworks_public"


def test_blockers_are_not_overwritten_by_weak_allowed_signal() -> None:
    record = SourceIntelligenceRecord(
        source_domain="realworks-enrich.test",
        access_status="allowed",
        has_captcha=True,
    )

    enriched = enrich_source_records_with_evidence([record], load_platform_evidence(EVIDENCE_FIXTURE))[0]

    assert enriched.has_captcha is True
    assert enriched.access_status == "blocked"
    assert enriched.delivery_mode == "captcha_blocked"


def test_enriched_report_reduces_unknown_manual_review_in_fixture(tmp_path: Path) -> None:
    source_master = tmp_path / "source-master.csv"
    _write_source_master(source_master)

    report = build_enriched_legacy_source_report(source_master, [EVIDENCE_FIXTURE])

    assert report["baseline_delivery_fingerprint"]["counts_by_delivery_mode"]["unknown_manual_review"] == 7
    assert report["delivery_fingerprint"]["counts_by_delivery_mode"]["unknown_manual_review"] == 1


def test_enriched_report_increases_parser_family_candidate_counts(tmp_path: Path) -> None:
    source_master = tmp_path / "source-master.csv"
    _write_source_master(source_master)

    report = build_enriched_legacy_source_report(source_master, [EVIDENCE_FIXTURE])

    candidates = report["delivery_fingerprint"]["counts_by_parser_family_candidate"]
    assert candidates["realworks_public"] == 1
    assert candidates["ogonline_xhr"] == 1
    assert candidates["wordpress_rest"] == 1


def test_build_enriched_report_integrates_all_layers(tmp_path: Path) -> None:
    source_master = tmp_path / "source-master.csv"
    _write_source_master(source_master)

    report = build_enriched_legacy_source_report(source_master, [EVIDENCE_FIXTURE])

    assert "source_intelligence" in report
    assert "access_policy" in report
    assert "delivery_fingerprint" in report
    assert "enrichment_summary" in report
    assert "is_active_audit" in report
    assert report["enrichment_summary"]["records_enriched_count"] == 7


def test_cli_writes_output_only_when_requested(tmp_path: Path) -> None:
    source_master = tmp_path / "source-master.csv"
    output_path = tmp_path / "report.json"
    _write_source_master(source_master)

    result = subprocess.run(
        [
            "py",
            "-3.12",
            "scripts/run_enriched_legacy_source_report.py",
            "--source-master",
            str(source_master),
            "--evidence",
            str(EVIDENCE_FIXTURE),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert output_path.exists()
    assert "records_enriched_count: 7" in result.stdout


def test_no_network_or_playwright_imports() -> None:
    module_text = Path("scraper/src/domek_wonen/sources/evidence_enrichment.py").read_text(encoding="utf-8")
    script_text = Path("scripts/run_enriched_legacy_source_report.py").read_text(encoding="utf-8")

    forbidden = ["requests", "httpx", "urllib.request", "playwright", "selenium"]
    assert not any(token in module_text for token in forbidden)
    assert not any(token in script_text for token in forbidden)


def test_load_legacy_records_still_works_with_fixture(tmp_path: Path) -> None:
    source_master = tmp_path / "source-master.csv"
    _write_source_master(source_master)

    records = load_legacy_source_records(source_master)

    assert len(records) == 8
