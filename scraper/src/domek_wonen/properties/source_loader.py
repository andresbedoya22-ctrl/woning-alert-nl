from __future__ import annotations

import csv
from pathlib import Path

from .models import PropertySource
from .platform_parser_registry import detect_platform_for_row, load_platform_assignments


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
        self.last_skipped_invalid_aanbod_url_count = 0

    def load(
        self,
        province: str,
        max_sources: int | None = None,
        *,
        include_invalid_sources: bool = False,
        platform_filter: str = "",
        platform_fingerprint_path: Path | None = None,
    ) -> list[PropertySource]:
        target_province = normalize_province(province)
        loaded: list[PropertySource] = []
        platform_assignments = load_platform_assignments(platform_fingerprint_path) if platform_fingerprint_path else {}
        normalized_platform_filter = (platform_filter or "").strip().lower()
        self.last_skipped_invalid_aanbod_url_count = 0
        if not self.csv_path.exists():
            raise MissingSourceFileError(self.csv_path)
        with self.csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                detected_platform = detect_platform_for_row(row, platform_assignments)
                if normalized_platform_filter and detected_platform != normalized_platform_filter:
                    continue
                source = self._build_source(
                    row,
                    include_invalid_sources=include_invalid_sources,
                    detected_platform=detected_platform,
                )
                if source is None:
                    continue
                if target_province and source.province != target_province:
                    continue
                loaded.append(source)
                if max_sources is not None and max_sources >= 0 and len(loaded) >= max_sources:
                    break
        return loaded

    def _build_source(
        self,
        row: dict[str, str],
        *,
        include_invalid_sources: bool,
        detected_platform: str,
    ) -> PropertySource | None:
        if (row.get("is_active") or "").strip().lower() != "true":
            return None
        if (row.get("legal_status") or "").strip() != "allowed_official_source":
            return None
        if (row.get("aanbod_url_quality") or "").strip() != "valid":
            return None
        aanbod_url_type = (row.get("aanbod_url_type") or "").strip() or "missing"
        source_quality_status = (row.get("source_quality_status") or "").strip()
        if not include_invalid_sources and (
            aanbod_url_type == "property_detail" or source_quality_status == "invalid"
        ):
            self.last_skipped_invalid_aanbod_url_count += 1
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
            aanbod_url_type=aanbod_url_type,
            source_quality_status=source_quality_status,
            source_quality_reason=(row.get("source_quality_reason") or "").strip(),
            is_active=True,
            source_origin=(row.get("source_origin") or "").strip(),
            detected_platform=detected_platform,
        )
