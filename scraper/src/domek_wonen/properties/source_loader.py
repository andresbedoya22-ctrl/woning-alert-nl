from __future__ import annotations

import csv
from pathlib import Path
from urllib.parse import urlsplit

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
    def __init__(self, csv_path: Path, *, override_csv_path: Path | None = None) -> None:
        self.csv_path = csv_path
        self.override_csv_path = override_csv_path
        self.last_skipped_invalid_aanbod_url_count = 0

    def load(
        self,
        province: str,
        max_sources: int | None = None,
        *,
        include_invalid_sources: bool = False,
        platform_filter: str = "",
        platform_fingerprint_path: Path | None = None,
        source_domain: str = "",
    ) -> list[PropertySource]:
        target_province = normalize_province(province)
        loaded: list[PropertySource] = []
        platform_assignments = load_platform_assignments(platform_fingerprint_path) if platform_fingerprint_path else {}
        normalized_platform_filter = (platform_filter or "").strip().lower()
        normalized_source_domain = _normalize_source_domain(source_domain)
        self.last_skipped_invalid_aanbod_url_count = 0
        if not self.csv_path.exists():
            raise MissingSourceFileError(self.csv_path)
        for row in self._iter_rows():
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
            if normalized_source_domain and source.root_domain != normalized_source_domain:
                continue
            if target_province and source.province != target_province:
                continue
            loaded.append(source)
            if max_sources is not None and max_sources >= 0 and len(loaded) >= max_sources:
                break
        return loaded

    def _iter_rows(self) -> list[dict[str, str]]:
        with self.csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            base_rows = list(csv.DictReader(handle))
        if self.override_csv_path is None or not self.override_csv_path.exists():
            return base_rows

        row_by_key: dict[tuple[str, str, str], dict[str, str]] = {}
        base_order: list[tuple[str, str, str]] = []
        for row in base_rows:
            key = _row_key(row)
            if key not in row_by_key:
                base_order.append(key)
            row_by_key[key] = row

        override_order: list[tuple[str, str, str]] = []
        with self.override_csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for override_row in csv.DictReader(handle):
                key = _row_key(override_row)
                override_order.append(key)
                base_row = row_by_key.get(key, {})
                row_by_key[key] = _merge_row(base_row, override_row)

        override_keys = set(override_order)
        merged_rows = [row_by_key[key] for key in override_order]
        merged_rows.extend(row_by_key[key] for key in base_order if key not in override_keys)
        return merged_rows

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


def _normalize_source_domain(value: str) -> str:
    normalized = (value or "").strip().lower()
    if not normalized:
        return ""
    if normalized.startswith(("http://", "https://")):
        return (urlsplit(normalized).netloc or "").strip().lower()
    return normalized.strip("/")


def _row_key(row: dict[str, str]) -> tuple[str, str, str]:
    source_id = (row.get("source_id") or "").strip().lower()
    if source_id:
        return ("source_id", source_id, "")
    root_domain = (row.get("root_domain") or "").strip().lower()
    gemeente = (row.get("gemeente") or "").strip().lower()
    province = normalize_province(row.get("province") or "").strip().lower()
    return (root_domain, gemeente, province)


def _merge_row(base_row: dict[str, str], override_row: dict[str, str]) -> dict[str, str]:
    merged = dict(base_row)
    for key, value in override_row.items():
        if value is None:
            continue
        if value != "":
            merged[key] = value
    return merged
