from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

import pytest

from domek_wonen.properties.source_loader import MissingSourceFileError, SourceLoader


def test_source_loader_keeps_only_active_official_valid_sources(tmp_path: Path) -> None:
    csv_path = tmp_path / "sources.csv"
    csv_path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website,gemeente,province,source_origin,aanbod_url,aanbod_url_quality,aanbod_url_type,confidence_score,source_quality_status,source_quality_reason,needs_review,review_reason,legal_status,last_seen_at,last_audited_at,is_active",
                "ok-1,Official One,official-one.nl,https://official-one.nl,Breda,Noord-Brabant,seed,https://official-one.nl/aanbod,valid,listing_index,80,valid,,false,,allowed_official_source,20260613T000000Z,,true",
                "bad-1,Inactive,inactive.nl,https://inactive.nl,Breda,Noord-Brabant,seed,https://inactive.nl/aanbod,valid,listing_index,80,valid,,false,,allowed_official_source,20260613T000000Z,,false",
                "bad-2,Suspect,suspect.nl,https://suspect.nl,Breda,Noord-Brabant,seed,https://suspect.nl/aanbod,valid,listing_index,80,valid,,false,,suspect,20260613T000000Z,,true",
                "bad-3,Funda,funda.nl,https://funda.nl,Breda,Noord-Brabant,aggregator,https://funda.nl/koop,valid,listing_index,80,valid,,false,,allowed_official_source,20260613T000000Z,,true",
                "bad-4,Detail,detail.nl,https://detail.nl,Breda,Noord-Brabant,seed,https://detail.nl/aanbod/woningaanbod/koop/huis-123-Markt-1,valid,property_detail,80,valid,,false,,allowed_official_source,20260613T000000Z,,true",
                "bad-5,Invalid,invalid.nl,https://invalid.nl,Breda,Noord-Brabant,seed,https://invalid.nl/contact,valid,listing_index,80,invalid,aanbod_url_type=commercial_page,false,,allowed_official_source,20260613T000000Z,,true",
            ]
        ),
        encoding="utf-8",
    )

    sources = SourceLoader(csv_path).load(province="noord-brabant")

    assert [source.source_id for source in sources] == ["ok-1"]
    assert SourceLoader(csv_path).load(province="noord-brabant", include_invalid_sources=True)[-2].source_id == "bad-4"


def test_source_loader_filters_by_source_domain(tmp_path: Path) -> None:
    csv_path = tmp_path / "sources.csv"
    csv_path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website,gemeente,province,source_origin,aanbod_url,aanbod_url_quality,aanbod_url_type,confidence_score,source_quality_status,source_quality_reason,needs_review,review_reason,legal_status,last_seen_at,last_audited_at,is_active",
                "ok-1,Official One,kinmakelaars.nl,https://kinmakelaars.nl,Breda,Noord-Brabant,seed,https://kinmakelaars.nl/aanbod,valid,listing_index,80,valid,,false,,allowed_official_source,20260613T000000Z,,true",
                "ok-2,Official Two,other.nl,https://other.nl,Breda,Noord-Brabant,seed,https://other.nl/aanbod,valid,listing_index,80,valid,,false,,allowed_official_source,20260613T000000Z,,true",
            ]
        ),
        encoding="utf-8",
    )

    sources = SourceLoader(csv_path).load(province="noord-brabant", source_domain="kinmakelaars.nl")

    assert [source.source_id for source in sources] == ["ok-1"]


def test_source_loader_raises_clear_error_when_csv_is_missing(tmp_path: Path) -> None:
    missing_path = tmp_path / "makelaar_sources_master.csv"

    with pytest.raises(MissingSourceFileError) as excinfo:
        SourceLoader(missing_path).load(province="noord-brabant")

    assert excinfo.value.csv_path == missing_path


def test_source_loader_merges_targeted_overrides_and_adds_missing_sources(tmp_path: Path) -> None:
    csv_path = tmp_path / "sources.csv"
    override_csv_path = tmp_path / "overrides.csv"
    csv_path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website,gemeente,province,source_origin,aanbod_url,aanbod_url_quality,aanbod_url_type,confidence_score,score,source_quality_status,source_quality_reason,needs_review,review_reason,legal_status,last_seen_at,last_audited_at,run_id,is_active",
                "allroundmakelaardij.nl__tilburg,Allround Makelaardij,allroundmakelaardij.nl,https://www.allroundmakelaardij.nl,Tilburg,Noord-Brabant,overpass_osm,,missing,missing,40,40,missing,,true,missing aanbod_url,missing,20260614T122022Z,,20260614T122022Z,false",
                "cvda.nl__tilburg,CVDA Makelaars en Taxateurs,cvda.nl,https://www.cvda.nl,Tilburg,Noord-Brabant,seed,https://www.cvda.nl/aanbod/woningaanbod,valid,listing_index,70,70,valid,derived_from_property_detail,true,url points to property detail page,needs_manual_review,20260614T122022Z,,20260614T122022Z,true",
            ]
        ),
        encoding="utf-8",
    )
    override_csv_path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website,gemeente,province,source_origin,aanbod_url,aanbod_url_quality,aanbod_url_type,confidence_score,score,source_quality_status,source_quality_reason,needs_review,review_reason,legal_status,last_seen_at,last_audited_at,run_id,is_active",
                "allroundmakelaardij.nl__tilburg,Allround Makelaardij,allroundmakelaardij.nl,https://www.allroundmakelaardij.nl,Tilburg,Noord-Brabant,property_discovery_supported_batch_v1,https://www.allroundmakelaardij.nl/woningen/,valid,listing_index,95,95,valid,approved,false,,allowed_official_source,20260616T000000Z,20260616T000000Z,20260616T000000Z,true",
                "cvda.nl__tilburg,CVDA Makelaars en Taxateurs,cvda.nl,https://www.cvda.nl,Tilburg,Noord-Brabant,property_discovery_supported_batch_v1,https://www.cvda.nl/aanbod/woningaanbod/,valid,listing_index,95,95,valid,approved,false,,allowed_official_source,20260616T000000Z,20260616T000000Z,20260616T000000Z,true",
                "jurgensmakelaardij.nl__tilburg,Jurgens Makelaardij,jurgensmakelaardij.nl,https://jurgensmakelaardij.nl,Tilburg,Noord-Brabant,property_discovery_supported_batch_v1,https://jurgensmakelaardij.nl/wonen/,valid,listing_index,95,95,valid,approved,false,,allowed_official_source,20260616T000000Z,20260616T000000Z,20260616T000000Z,true",
            ]
        ),
        encoding="utf-8",
    )

    sources = SourceLoader(csv_path, override_csv_path=override_csv_path).load(province="noord-brabant")

    assert [source.source_id for source in sources] == [
        "allroundmakelaardij.nl__tilburg",
        "cvda.nl__tilburg",
        "jurgensmakelaardij.nl__tilburg",
    ]
    assert sources[0].aanbod_url == "https://www.allroundmakelaardij.nl/woningen/"
    assert sources[0].legal_status == "allowed_official_source"
    assert sources[1].aanbod_url == "https://www.cvda.nl/aanbod/woningaanbod/"
    assert sources[2].root_domain == "jurgensmakelaardij.nl"
