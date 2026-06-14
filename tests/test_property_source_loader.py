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
                "source_id,office_name,root_domain,website,gemeente,province,source_origin,aanbod_url,aanbod_url_quality,confidence_score,needs_review,review_reason,legal_status,last_seen_at,last_audited_at,is_active",
                "ok-1,Official One,official-one.nl,https://official-one.nl,Breda,Noord-Brabant,seed,https://official-one.nl/aanbod,valid,80,false,,allowed_official_source,20260613T000000Z,,true",
                "bad-1,Inactive,inactive.nl,https://inactive.nl,Breda,Noord-Brabant,seed,https://inactive.nl/aanbod,valid,80,false,,allowed_official_source,20260613T000000Z,,false",
                "bad-2,Suspect,suspect.nl,https://suspect.nl,Breda,Noord-Brabant,seed,https://suspect.nl/aanbod,valid,80,false,,suspect,20260613T000000Z,,true",
                "bad-3,Funda,funda.nl,https://funda.nl,Breda,Noord-Brabant,aggregator,https://funda.nl/koop,valid,80,false,,allowed_official_source,20260613T000000Z,,true",
            ]
        ),
        encoding="utf-8",
    )

    sources = SourceLoader(csv_path).load(province="noord-brabant")

    assert [source.source_id for source in sources] == ["ok-1"]


def test_source_loader_raises_clear_error_when_csv_is_missing(tmp_path: Path) -> None:
    missing_path = tmp_path / "makelaar_sources_master.csv"

    with pytest.raises(MissingSourceFileError) as excinfo:
        SourceLoader(missing_path).load(province="noord-brabant")

    assert excinfo.value.csv_path == missing_path
