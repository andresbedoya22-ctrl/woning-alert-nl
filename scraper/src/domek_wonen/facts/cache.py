from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .models import FACT_SCHEMA_VERSION, PropertyFactsRecord, record_from_dict, record_to_dict


class PropertyFactsCache:
    def __init__(self, path: Path):
        self.path = Path(path)

    def load_all(self) -> tuple[PropertyFactsRecord, ...]:
        if not self.path.exists():
            return ()
        records: list[PropertyFactsRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
                records.append(record_from_dict(payload))
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
        return tuple(records)

    def get(self, canonical_url: str, source_domain: str) -> PropertyFactsRecord | None:
        matches = tuple(
            record
            for record in self.load_all()
            if record.canonical_url == canonical_url
            and record.source_domain == source_domain
            and record.schema_version == FACT_SCHEMA_VERSION
        )
        if not matches:
            return None
        return sorted(matches, key=lambda record: _parse_datetime(record.fetched_at) or datetime.min.replace(tzinfo=UTC))[-1]

    def upsert(self, record: PropertyFactsRecord) -> None:
        self.upsert_many((record,))

    def upsert_many(self, records: Iterable[PropertyFactsRecord]) -> None:
        by_key: dict[tuple[str, str, str], PropertyFactsRecord] = {
            _cache_key(record): record for record in self.load_all()
        }
        for record in records:
            key = _cache_key(record)
            current = by_key.get(key)
            if current is None or _is_newer(record, current):
                by_key[key] = record
        ordered = tuple(sorted(by_key.values(), key=lambda item: (item.source_domain, item.canonical_url, item.schema_version)))
        self._write_records(ordered)

    def is_stale(self, record: PropertyFactsRecord, now: datetime) -> bool:
        if record.schema_version != FACT_SCHEMA_VERSION:
            return True
        now = _ensure_aware(now)
        if record.expires_at:
            expires = _parse_datetime(record.expires_at)
            return expires is None or expires <= now
        fetched = _parse_datetime(record.fetched_at)
        if fetched is None:
            return True
        return fetched + timedelta(days=14) <= now

    def _write_records(self, records: tuple[PropertyFactsRecord, ...]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_name(f"{self.path.name}.tmp")
        lines = [json.dumps(record_to_dict(record), ensure_ascii=False, sort_keys=True) for record in records]
        temp_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        temp_path.replace(self.path)


def _cache_key(record: PropertyFactsRecord) -> tuple[str, str, str]:
    return (record.source_domain, record.canonical_url, record.schema_version)


def _is_newer(candidate: PropertyFactsRecord, current: PropertyFactsRecord) -> bool:
    candidate_time = _parse_datetime(candidate.fetched_at)
    current_time = _parse_datetime(current.fetched_at)
    if candidate_time is None:
        return False
    if current_time is None:
        return True
    return candidate_time > current_time


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return _ensure_aware(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        return None


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
