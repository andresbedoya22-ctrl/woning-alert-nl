from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.inventory.models import InventorySnapshot, InventorySource, NormalizedListing


def test_inventory_source_can_run_only_when_allowed_or_limited() -> None:
    assert InventorySource(source_id="a", source_domain="a.test", access_status="allowed").can_run is True
    assert InventorySource(source_id="b", source_domain="b.test", access_status="limited").can_run is True
    assert InventorySource(source_id="c", source_domain="c.test", access_status="blocked").can_run is False
    assert InventorySource(source_id="d", source_domain="d.test", access_status="permission_required").can_run is False


def test_normalized_listing_stable_key_normalizes_url_variants() -> None:
    first = NormalizedListing(
        source_id="source-a",
        source_domain="example.test",
        canonical_url="http://example.test/woning/alpha-1/?utm_source=x",
        asking_price_eur=300000,
        status="beschikbaar",
        transaction_type="koop",
    )
    second = NormalizedListing(
        source_id="source-a",
        source_domain="example.test",
        canonical_url="https://example.test/woning/alpha-1/",
        asking_price_eur=300000,
        status="beschikbaar",
        transaction_type="koop",
    )

    assert first.normalized_url() == "https://example.test/woning/alpha-1"
    assert first.stable_key() == second.stable_key()


def test_normalized_listing_comparable_hash_changes_when_price_changes() -> None:
    before = NormalizedListing(
        source_id="source-a",
        source_domain="example.test",
        canonical_url="https://example.test/woning/alpha-1/",
        asking_price_eur=300000,
        status="beschikbaar",
        transaction_type="koop",
    )
    after = NormalizedListing(
        source_id="source-a",
        source_domain="example.test",
        canonical_url="https://example.test/woning/alpha-1/",
        asking_price_eur=310000,
        status="beschikbaar",
        transaction_type="koop",
    )

    assert before.stable_key() == after.stable_key()
    assert before.comparable_hash() != after.comparable_hash()


def test_inventory_snapshot_deduplicates_by_stable_key_preferring_confidence() -> None:
    weak = NormalizedListing(
        source_id="source-a",
        source_domain="example.test",
        canonical_url="https://example.test/woning/alpha-1/",
        asking_price_eur=None,
        confidence_score=0.2,
    )
    strong = NormalizedListing(
        source_id="source-a",
        source_domain="example.test",
        canonical_url="https://example.test/woning/alpha-1/",
        asking_price_eur=300000,
        confidence_score=0.9,
    )

    snapshot = InventorySnapshot(snapshot_id="test", captured_at="2026-06-22T08:00:00Z", listings=(weak, strong))

    deduped = snapshot.by_stable_key()
    assert len(deduped) == 1
    assert next(iter(deduped.values())).asking_price_eur == 300000
