from __future__ import annotations

import csv
from pathlib import Path

from .models import PropertySource


class MissingSourceFileError(FileNotFoundError):
    def __init__(self, csv_path: Path) -> None:
        self.csv_path = csv_path
        super().__init__(str(csv_path))


def normalize_province(value: str) -> str:
    normalized = (value or "").strip().lower().replace("_", "-").replace(" ", "-")
    aliases = {
        "noord-brabant": "Noord-Brabant",
    }
    return aliases.get(normalized, (value or "").strip())


class SourceLoader:
    def __init__(self, csv_path: Path) -> None:
        self.csv_path = csv_path

    def load(self, province: str, max_sources: int | None = None) -> list[PropertySource]:
        target_province = normalize_province(province)
        loaded: list[PropertySource] = []
        if not self.csv_path.exists():
            raise MissingSourceFileError(self.csv_path)
        with self.csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                source = self._build_source(row)
                if source is None:
                    continue
                if target_province and source.province != target_province:
                    continue
                loaded.append(source)
                if max_sources is not None and max_sources >= 0 and len(loaded) >= max_sources:
                    break
        return loaded

    def _build_source(self, row: dict[str, str]) -> PropertySource | None:
        if (row.get("is_active") or "").strip().lower() != "true":
            return None
        if (row.get("legal_status") or "").strip() != "allowed_official_source":
            return None
        if (row.get("aanbod_url_quality") or "").strip() != "valid":
            return None

        root_domain = (row.get("root_domain") or "").strip().lower()
        website = (row.get("website") or "").strip()
        aanbod_url = (row.get("aanbod_url") or "").strip()
        source_origin = (row.get("source_origin") or "").strip().lower()
        joined_text = " ".join([root_domain, website.lower(), aanbod_url.lower(), source_origin])
        disallowed_tokens = ("funda", "aggregator", "jaap", "huispedia")
        if any(token in joined_text for token in disallowed_tokens):
            return None

        return PropertySource(
            source_id=(row.get("source_id") or "").strip(),
            office_name=(row.get("office_name") or "").strip(),
            root_domain=root_domain,
            website=website,
            aanbod_url=aanbod_url,
            gemeente=(row.get("gemeente") or "").strip(),
            province=(row.get("province") or "").strip(),
            legal_status=(row.get("legal_status") or "").strip(),
            aanbod_url_quality=(row.get("aanbod_url_quality") or "").strip(),
            is_active=True,
            source_origin=(row.get("source_origin") or "").strip(),
        )
