from __future__ import annotations

import csv
from pathlib import Path
from typing import Protocol

from .platform_parsers import RealworksParser


class PlatformParser(Protocol):
    def parse(
        self,
        source,
        *,
        max_properties_per_source: int,
        page_timeout_seconds: int,
    ): ...


def load_platform_assignments(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}

    assignments: dict[str, str] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            detected_platform = (row.get("detected_platform") or "").strip().lower()
            if not detected_platform:
                continue
            source_id = (row.get("source_id") or "").strip().lower()
            root_domain = (row.get("root_domain") or "").strip().lower()
            if source_id:
                assignments[f"source_id:{source_id}"] = detected_platform
            if root_domain:
                assignments[f"root_domain:{root_domain}"] = detected_platform
    return assignments


def detect_platform_for_row(row: dict[str, str], assignments: dict[str, str]) -> str:
    source_id = (row.get("source_id") or "").strip().lower()
    root_domain = (row.get("root_domain") or "").strip().lower()
    if source_id and f"source_id:{source_id}" in assignments:
        return assignments[f"source_id:{source_id}"]
    if root_domain and f"root_domain:{root_domain}" in assignments:
        return assignments[f"root_domain:{root_domain}"]
    return ""


def get_platform_parser(platform_name: str) -> PlatformParser | None:
    normalized = (platform_name or "").strip().lower()
    if normalized == "realworks":
        return RealworksParser()
    return None
