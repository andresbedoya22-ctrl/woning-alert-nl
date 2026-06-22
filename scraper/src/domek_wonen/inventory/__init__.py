"""Inventory core for WoningAlert NL.

This package owns deterministic inventory state and daily diff logic.
It intentionally does not fetch live websites. Source adapters and parser
families should feed normalized listings into this layer.
"""

from domek_wonen.inventory.diff_engine import InventoryDiffEngine
from domek_wonen.inventory.fixture_adapter import FixtureInventoryAdapter
from domek_wonen.inventory.models import (
    InventoryChange,
    InventoryDiffResult,
    InventoryItem,
    InventorySnapshot,
    InventorySource,
    NormalizedListing,
    RawListing,
)

__all__ = [
    "FixtureInventoryAdapter",
    "InventoryChange",
    "InventoryDiffEngine",
    "InventoryDiffResult",
    "InventoryItem",
    "InventorySnapshot",
    "InventorySource",
    "NormalizedListing",
    "RawListing",
]
