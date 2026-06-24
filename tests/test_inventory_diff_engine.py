from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.inventory import FixtureInventoryAdapter, InventoryDiffEngine, InventorySnapshot, NormalizedListing

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "inventory"


def test_inventory_diff_engine_detects_expected_daily_changes() -> None:
    adapter = FixtureInventoryAdapter()
    previous = adapter.load_snapshot(FIXTURE_DIR / "day_1.json")
    current = adapter.load_snapshot(FIXTURE_DIR / "day_2.json")

    result = InventoryDiffEngine().compare(previous, current)
    counts = result.counts_by_type()

    assert counts["new"] == 1
    assert counts["removed"] == 1
    assert counts["price_changed"] == 1
    assert counts["status_changed"] == 1
    assert counts["unchanged"] == 2
    assert result.source_failures == {"temporarily-stale-source": "timeout"}


def test_inventory_diff_engine_keeps_url_variants_unchanged() -> None:
    previous = InventorySnapshot(
        snapshot_id="previous",
        captured_at="2026-06-22T08:00:00Z",
        listings=(
            NormalizedListing(
                source_id="source-a",
                source_domain="example.test",
                canonical_url="http://example.test/woning/alpha-1/?utm_source=x",
                asking_price_eur=300000,
                transaction_type="koop",
                status="beschikbaar",
            ),
        ),
    )
    current = InventorySnapshot(
        snapshot_id="current",
        captured_at="2026-06-23T08:00:00Z",
        listings=(
            NormalizedListing(
                source_id="source-a",
                source_domain="example.test",
                canonical_url="https://example.test/woning/alpha-1/",
                asking_price_eur=300000,
                transaction_type="koop",
                status="beschikbaar",
            ),
        ),
    )

    result = InventoryDiffEngine().compare(previous, current)

    assert result.counts_by_type() == {"unchanged": 1}


def test_inventory_diff_engine_reports_price_and_status_when_both_change() -> None:
    previous = InventorySnapshot(
        snapshot_id="previous",
        captured_at="2026-06-22T08:00:00Z",
        listings=(
            NormalizedListing(
                source_id="source-a",
                source_domain="example.test",
                canonical_url="https://example.test/woning/alpha-1/",
                asking_price_eur=300000,
                transaction_type="koop",
                status="beschikbaar",
            ),
        ),
    )
    current = InventorySnapshot(
        snapshot_id="current",
        captured_at="2026-06-23T08:00:00Z",
        listings=(
            NormalizedListing(
                source_id="source-a",
                source_domain="example.test",
                canonical_url="https://example.test/woning/alpha-1/",
                asking_price_eur=310000,
                transaction_type="koop",
                status="onder_bod",
            ),
        ),
    )

    result = InventoryDiffEngine().compare(previous, current)
    change = result.changes[0]

    assert change.change_type == "price_and_status_changed"
    assert change.changed_fields == ("asking_price_eur", "status")


def test_fixture_inventory_adapter_rejects_invalid_fixture_shape(tmp_path: Path) -> None:
    bad_fixture = tmp_path / "bad.json"
    bad_fixture.write_text("[]", encoding="utf-8")

    adapter = FixtureInventoryAdapter()

    try:
        adapter.load_snapshot(bad_fixture)
    except ValueError as error:
        assert "JSON object" in str(error)
    else:
        raise AssertionError("Expected invalid fixture shape to raise ValueError")
