from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Iterable


class FreshnessBucket(StrEnum):
    NEW_TODAY = "new_today"
    NEW_3D = "new_3d"
    NEW_7D = "new_7d"
    NEW_14D = "new_14d"
    STALE_30D = "stale_30d"
    STALE_60D = "stale_60d"
    STALE_90D_PLUS = "stale_90d_plus"
    UNKNOWN_AGE = "unknown_age"


class LifecycleEvent(StrEnum):
    NEW_LISTING = "new_listing"
    PRICE_CHANGED = "price_changed"
    STATUS_CHANGED = "status_changed"
    UNDER_OFFER = "under_offer"
    SOLD = "sold"
    REMOVED = "removed"
    REAPPEARED = "reappeared"
    NON_RESIDENTIAL_EXCLUDED = "non_residential_excluded"


class LifecycleStatus(StrEnum):
    USABLE = "usable"
    REVIEW = "review"
    MISSING = "missing"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class ListingLifecycleFields:
    source_published_at: datetime | None = None
    source_published_at_raw: str | None = None
    source_published_at_source: str | None = None
    source_published_at_status: str = LifecycleStatus.MISSING.value
    source_published_at_review_reason: str | None = None
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    observed_at: datetime | None = None
    status_first_seen_at: datetime | None = None
    status_changed_at: datetime | None = None
    price_first_seen_at: datetime | None = None
    price_changed_at: datetime | None = None
    removed_at: datetime | None = None
    days_on_market_source: int | None = None
    days_since_first_seen: int | None = None
    freshness_bucket: str = FreshnessBucket.UNKNOWN_AGE.value
    lifecycle_events: tuple[str, ...] = ()
    canonical_url: str | None = None
    normalized_key: str | None = None
    source_id: str | None = None
    asking_price: int | None = None
    status_bucket: str | None = None
    residential_classification: str | None = None


def build_initial_lifecycle_fields(
    *,
    canonical_url: str | None,
    normalized_key: str | None,
    source_id: str,
    source_published_at: datetime | date | str | None,
    source_published_at_status: str,
    source_published_at_raw: str | None = None,
    source_published_at_source: str | None = None,
    source_published_at_review_reason: str | None = None,
    asking_price: int | None,
    status_bucket: str,
    residential_classification: str,
    observed_at: datetime,
    previous_lifecycle_record: ListingLifecycleFields | None = None,
) -> ListingLifecycleFields:
    observed = _to_utc_datetime(observed_at)
    published = _coerce_datetime(source_published_at)
    previous = previous_lifecycle_record
    first_seen = previous.first_seen_at if previous and previous.first_seen_at else observed
    status_first_seen = previous.status_first_seen_at if previous and previous.status_first_seen_at else observed
    price_first_seen = previous.price_first_seen_at if previous and previous.price_first_seen_at else observed
    events: list[str] = []

    if previous is None:
        events.append(LifecycleEvent.NEW_LISTING.value)
    else:
        previous_removed = previous.removed_at is not None
        if previous_removed:
            events.append(LifecycleEvent.REAPPEARED.value)
        if previous.asking_price != asking_price:
            events.append(LifecycleEvent.PRICE_CHANGED.value)
        if previous.status_bucket != status_bucket:
            events.append(LifecycleEvent.STATUS_CHANGED.value)

    if _is_under_offer(status_bucket):
        events.append(LifecycleEvent.UNDER_OFFER.value)
    if _is_sold(status_bucket):
        events.append(LifecycleEvent.SOLD.value)
    if residential_classification.startswith("non_residential"):
        events.append(LifecycleEvent.NON_RESIDENTIAL_EXCLUDED.value)

    status_changed_at = observed if previous and previous.status_bucket != status_bucket else None
    price_changed_at = observed if previous and previous.asking_price != asking_price else None

    return ListingLifecycleFields(
        source_published_at=published,
        source_published_at_raw=source_published_at_raw,
        source_published_at_source=source_published_at_source,
        source_published_at_status=source_published_at_status or LifecycleStatus.MISSING.value,
        source_published_at_review_reason=source_published_at_review_reason,
        first_seen_at=first_seen,
        last_seen_at=observed,
        observed_at=observed,
        status_first_seen_at=status_first_seen,
        status_changed_at=status_changed_at,
        price_first_seen_at=price_first_seen,
        price_changed_at=price_changed_at,
        removed_at=None,
        days_on_market_source=compute_days_on_market(published, observed),
        days_since_first_seen=compute_days_on_market(first_seen, observed),
        freshness_bucket=compute_freshness_bucket(
            source_published_at=published,
            first_seen_at=first_seen,
            observed_at=observed,
        ),
        lifecycle_events=_dedupe(events),
        canonical_url=canonical_url,
        normalized_key=normalized_key,
        source_id=source_id,
        asking_price=asking_price,
        status_bucket=status_bucket,
        residential_classification=residential_classification,
    )


def compute_days_on_market(started_at: datetime | date | str | None, observed_at: datetime | date | str | None) -> int | None:
    started = _coerce_datetime(started_at)
    observed = _coerce_datetime(observed_at)
    if started is None or observed is None:
        return None
    return max(0, (observed.date() - started.date()).days)


def compute_freshness_bucket(
    *,
    source_published_at: datetime | date | str | None = None,
    first_seen_at: datetime | date | str | None = None,
    observed_at: datetime | date | str | None,
) -> str:
    observed = _coerce_datetime(observed_at)
    if observed is None:
        return FreshnessBucket.UNKNOWN_AGE.value
    reference = _coerce_datetime(source_published_at) or _coerce_datetime(first_seen_at)
    if reference is None:
        return FreshnessBucket.UNKNOWN_AGE.value
    age_days = max(0, (observed.date() - reference.date()).days)
    if age_days == 0:
        return FreshnessBucket.NEW_TODAY.value
    if age_days <= 3:
        return FreshnessBucket.NEW_3D.value
    if age_days <= 7:
        return FreshnessBucket.NEW_7D.value
    if age_days <= 14:
        return FreshnessBucket.NEW_14D.value
    if age_days <= 30:
        return FreshnessBucket.STALE_30D.value
    if age_days <= 60:
        return FreshnessBucket.STALE_60D.value
    return FreshnessBucket.STALE_90D_PLUS.value


def compare_lifecycle(
    previous_record: ListingLifecycleFields | None,
    current_record: ListingLifecycleFields,
) -> ListingLifecycleFields:
    if previous_record is None:
        if LifecycleEvent.NEW_LISTING.value in current_record.lifecycle_events:
            return current_record
        return replace(
            current_record,
            lifecycle_events=_dedupe((*current_record.lifecycle_events, LifecycleEvent.NEW_LISTING.value)),
        )
    observed = current_record.observed_at or current_record.last_seen_at
    if observed is None:
        return current_record
    return build_initial_lifecycle_fields(
        canonical_url=current_record.canonical_url,
        normalized_key=current_record.normalized_key,
        source_id=current_record.source_id or "",
        source_published_at=current_record.source_published_at,
        source_published_at_raw=current_record.source_published_at_raw,
        source_published_at_source=current_record.source_published_at_source,
        source_published_at_status=current_record.source_published_at_status,
        source_published_at_review_reason=current_record.source_published_at_review_reason,
        asking_price=current_record.asking_price,
        status_bucket=current_record.status_bucket or "",
        residential_classification=current_record.residential_classification or "",
        observed_at=observed,
        previous_lifecycle_record=previous_record,
    )


def build_removed_lifecycle_fields(
    previous_record: ListingLifecycleFields,
    *,
    observed_at: datetime,
) -> ListingLifecycleFields:
    observed = _to_utc_datetime(observed_at)
    return replace(
        previous_record,
        last_seen_at=previous_record.last_seen_at,
        observed_at=observed,
        removed_at=observed,
        lifecycle_events=_dedupe((*previous_record.lifecycle_events, LifecycleEvent.REMOVED.value)),
    )


def compare_removed_keys(
    previous_records: Iterable[ListingLifecycleFields],
    current_keys: Iterable[str],
    *,
    observed_at: datetime,
) -> tuple[ListingLifecycleFields, ...]:
    current_key_set = set(current_keys)
    removed: list[ListingLifecycleFields] = []
    for record in previous_records:
        key = record.normalized_key or record.canonical_url
        if key and key not in current_key_set:
            removed.append(build_removed_lifecycle_fields(record, observed_at=observed_at))
    return tuple(removed)


def _coerce_datetime(value: datetime | date | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _to_utc_datetime(value)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    text = str(value).strip()
    if not text:
        return None
    try:
        return _to_utc_datetime(datetime.fromisoformat(text.replace("Z", "+00:00")))
    except ValueError:
        return None


def _to_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _is_under_offer(status_bucket: str) -> bool:
    return status_bucket in {"inactive_under_offer", "inactive_under_contract"}


def _is_sold(status_bucket: str) -> bool:
    return status_bucket == "inactive_sold"


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)
