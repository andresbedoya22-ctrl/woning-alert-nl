from __future__ import annotations

from domek_wonen.inventory.models import (
    InventoryChange,
    InventoryDiffResult,
    InventorySnapshot,
    NormalizedListing,
)


class InventoryDiffEngine:
    """Compare two inventory snapshots and return deterministic changes.

    This engine does not fetch data and does not decide whether a source may be
    used. It only compares normalized listings that upstream adapters/parsers
    already produced.
    """

    def compare(self, previous: InventorySnapshot, current: InventorySnapshot) -> InventoryDiffResult:
        previous_by_key = previous.by_stable_key()
        current_by_key = current.by_stable_key()
        all_keys = sorted(set(previous_by_key) | set(current_by_key))

        changes: list[InventoryChange] = []
        for key in all_keys:
            before = previous_by_key.get(key)
            after = current_by_key.get(key)

            if before is None and after is not None:
                changes.append(
                    InventoryChange(
                        change_type="new",
                        inventory_id=key,
                        after=after,
                        reason="listing appears in current snapshot only",
                    )
                )
                continue

            if before is not None and after is None:
                changes.append(
                    InventoryChange(
                        change_type="removed",
                        inventory_id=key,
                        before=before,
                        reason="listing appears in previous snapshot only",
                    )
                )
                continue

            if before is None or after is None:
                continue

            changed_fields = self._changed_fields(before, after)
            if not changed_fields:
                changes.append(
                    InventoryChange(
                        change_type="unchanged",
                        inventory_id=key,
                        before=before,
                        after=after,
                    )
                )
                continue

            changes.append(
                InventoryChange(
                    change_type=self._change_type(changed_fields),
                    inventory_id=key,
                    before=before,
                    after=after,
                    changed_fields=tuple(changed_fields),
                    reason="; ".join(changed_fields),
                )
            )

        return InventoryDiffResult(
            previous_snapshot_id=previous.snapshot_id,
            current_snapshot_id=current.snapshot_id,
            changes=tuple(changes),
            source_failures=dict(current.source_failures),
        )

    @staticmethod
    def _changed_fields(before: NormalizedListing, after: NormalizedListing) -> list[str]:
        changed: list[str] = []
        if before.asking_price_eur != after.asking_price_eur:
            changed.append("asking_price_eur")
        if before.status != after.status:
            changed.append("status")
        if before.transaction_type != after.transaction_type:
            changed.append("transaction_type")
        if before.comparable_hash() != after.comparable_hash() and not changed:
            changed.append("content_hash")
        return changed

    @staticmethod
    def _change_type(changed_fields: list[str]) -> str:
        if "asking_price_eur" in changed_fields and "status" in changed_fields:
            return "price_and_status_changed"
        if "asking_price_eur" in changed_fields:
            return "price_changed"
        if "status" in changed_fields:
            return "status_changed"
        if "transaction_type" in changed_fields:
            return "transaction_type_changed"
        return "content_changed"
