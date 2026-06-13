from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.properties.property_discovery_engine import run_property_discovery


def test_property_discovery_engine_handles_zero_max_sources_without_browser(tmp_path: Path) -> None:
    csv_path = tmp_path / "sources.csv"
    csv_path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website,gemeente,province,source_origin,aanbod_url,aanbod_url_quality,confidence_score,needs_review,review_reason,legal_status,last_seen_at,last_audited_at,is_active",
                "ok-1,Official One,official-one.nl,https://official-one.nl,Breda,Noord-Brabant,seed,https://official-one.nl/aanbod,valid,80,false,,allowed_official_source,20260613T000000Z,,true",
            ]
        ),
        encoding="utf-8",
    )

    output = run_property_discovery(
        province="noord-brabant",
        max_sources=0,
        max_properties_per_source=50,
        source_csv_path=csv_path,
        runs_base_dir=tmp_path / "runs",
        latest_dir=tmp_path / "latest",
    )

    assert output.sources_loaded == 0
    assert output.sources_attempted == 0
    assert (output.run_dir / "property_candidates.csv").exists()
    assert (output.latest_dir / "property_inventory.csv").exists()
