from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from domek_wonen.inventory.models import InventorySnapshot, NormalizedListing


class FixtureInventoryAdapter:
    """Load deterministic inventory snapshots from JSON fixtures.

    This adapter is intentionally offline-only. It allows the inventory core to
    be developed and tested before live portal or makelaar adapters exist.
    """

    def load_snapshot(self, fixture_path: Path) -> InventorySnapshot:
        with fixture_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        if not isinstance(payload, dict):
            raise ValueError("Inventory fixture must be a JSON object")

        snapshot_id = str(payload.get("snapshot_id") or fixture_path.stem)
        captured_at = str(payload.get("captured_at") or "")
        source_failures = payload.get("source_failures") or {}
        listings_payload = payload.get("listings") or []

        if not isinstance(source_failures, dict):
            raise ValueError("source_failures must be an object")
        if not isinstance(listings_payload, list):
            raise ValueError("listings must be a list")

        listings = tuple(self._parse_listing(item) for item in listings_payload)
        return InventorySnapshot(
            snapshot_id=snapshot_id,
            captured_at=captured_at,
            listings=listings,
            source_failures={str(key): str(value) for key, value in source_failures.items()},
        )

    def _parse_listing(self, payload: dict[str, Any]) -> NormalizedListing:
        if not isinstance(payload, dict):
            raise ValueError("listing entries must be JSON objects")

        return NormalizedListing(
            source_id=str(payload.get("source_id") or ""),
            source_domain=str(payload.get("source_domain") or ""),
            canonical_url=str(payload.get("canonical_url") or ""),
            address_raw=str(payload.get("address_raw") or ""),
            street=str(payload.get("street") or ""),
            house_number=str(payload.get("house_number") or ""),
            postcode=str(payload.get("postcode") or ""),
            city=str(payload.get("city") or ""),
            asking_price_eur=self._optional_int(payload.get("asking_price_eur")),
            transaction_type=str(payload.get("transaction_type") or "unknown"),
            status=str(payload.get("status") or "unknown"),
            living_area_m2=self._optional_int(payload.get("living_area_m2")),
            plot_area_m2=self._optional_int(payload.get("plot_area_m2")),
            rooms_count=self._optional_int(payload.get("rooms_count")),
            bedrooms_count=self._optional_int(payload.get("bedrooms_count")),
            energy_label=str(payload.get("energy_label") or ""),
            property_type=str(payload.get("property_type") or ""),
            external_id=str(payload.get("external_id") or ""),
            content_hash=str(payload.get("content_hash") or ""),
            confidence_score=float(payload.get("confidence_score") or 0.0),
            first_seen_at=str(payload.get("first_seen_at") or ""),
            last_seen_at=str(payload.get("last_seen_at") or ""),
            evidence=str(payload.get("evidence") or ""),
            needs_review=bool(payload.get("needs_review") or False),
            review_reason=str(payload.get("review_reason") or ""),
        )

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value in {None, ""}:
            return None
        return int(value)
