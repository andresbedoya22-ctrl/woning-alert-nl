from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import sys


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.inventory.lifecycle import (  # noqa: E402
    LifecycleEvent,
    ListingLifecycleFields,
    build_initial_lifecycle_fields,
    compute_freshness_bucket,
)


OBSERVED = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)


def _lifecycle(**overrides: object) -> ListingLifecycleFields:
    values = {
        "canonical_url": "https://example.nl/listing-1",
        "normalized_key": "example.nl|listing-1",
        "source_id": "example.nl__test",
        "source_published_at": None,
        "source_published_at_status": "missing",
        "asking_price": 425000,
        "status_bucket": "active_available",
        "residential_classification": "residential",
        "observed_at": OBSERVED,
    }
    values.update(overrides)
    return build_initial_lifecycle_fields(**values)


def test_new_listing_creates_new_listing_event() -> None:
    result = _lifecycle()

    assert result.lifecycle_events == (LifecycleEvent.NEW_LISTING.value,)


def test_first_seen_and_last_seen_equal_observed_on_initial_observation() -> None:
    result = _lifecycle()

    assert result.first_seen_at == OBSERVED
    assert result.last_seen_at == OBSERVED


def test_previous_first_seen_is_preserved() -> None:
    previous = _lifecycle(observed_at=datetime(2026, 6, 20, tzinfo=UTC))

    result = _lifecycle(previous_lifecycle_record=previous)

    assert result.first_seen_at == datetime(2026, 6, 20, tzinfo=UTC)
    assert result.last_seen_at == OBSERVED


def test_price_change_creates_price_changed() -> None:
    previous = _lifecycle(asking_price=400000)

    result = _lifecycle(asking_price=425000, previous_lifecycle_record=previous)

    assert LifecycleEvent.PRICE_CHANGED.value in result.lifecycle_events
    assert result.price_changed_at == OBSERVED


def test_status_change_creates_status_changed() -> None:
    previous = _lifecycle(status_bucket="active_available")

    result = _lifecycle(status_bucket="inactive_under_offer", previous_lifecycle_record=previous)

    assert LifecycleEvent.STATUS_CHANGED.value in result.lifecycle_events
    assert result.status_changed_at == OBSERVED


def test_status_to_sold_creates_sold() -> None:
    result = _lifecycle(status_bucket="inactive_sold")

    assert LifecycleEvent.SOLD.value in result.lifecycle_events


def test_status_to_under_contract_creates_under_offer() -> None:
    result = _lifecycle(status_bucket="inactive_under_contract")

    assert LifecycleEvent.UNDER_OFFER.value in result.lifecycle_events


def test_missing_source_published_at_uses_first_seen_bucket_when_available() -> None:
    result = _lifecycle(source_published_at=None)

    assert result.freshness_bucket == "new_today"
    assert result.days_since_first_seen == 0


def test_unknown_age_when_no_source_date_or_first_seen() -> None:
    bucket = compute_freshness_bucket(source_published_at=None, first_seen_at=None, observed_at=OBSERVED)

    assert bucket == "unknown_age"


def test_freshness_buckets() -> None:
    assert compute_freshness_bucket(source_published_at=datetime(2026, 6, 28, tzinfo=UTC), observed_at=OBSERVED) == "new_today"
    assert compute_freshness_bucket(source_published_at=datetime(2026, 6, 25, tzinfo=UTC), observed_at=OBSERVED) == "new_3d"
    assert compute_freshness_bucket(source_published_at=datetime(2026, 6, 21, tzinfo=UTC), observed_at=OBSERVED) == "new_7d"
    assert compute_freshness_bucket(source_published_at=datetime(2026, 6, 14, tzinfo=UTC), observed_at=OBSERVED) == "new_14d"
    assert compute_freshness_bucket(source_published_at=datetime(2026, 6, 1, tzinfo=UTC), observed_at=OBSERVED) == "stale_30d"
    assert compute_freshness_bucket(source_published_at=datetime(2026, 5, 1, tzinfo=UTC), observed_at=OBSERVED) == "stale_60d"
    assert compute_freshness_bucket(source_published_at=datetime(2026, 3, 1, tzinfo=UTC), observed_at=OBSERVED) == "stale_90d_plus"


def test_non_residential_creates_non_residential_excluded() -> None:
    result = _lifecycle(residential_classification="non_residential_blocked")

    assert LifecycleEvent.NON_RESIDENTIAL_EXCLUDED.value in result.lifecycle_events
