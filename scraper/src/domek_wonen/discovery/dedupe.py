from __future__ import annotations

import re

from .models import SourceCandidate


def normalize_office_name(value: str) -> str:
    lowered = (value or "").strip().lower()
    collapsed = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(collapsed.split())


def _candidate_rank(candidate: SourceCandidate) -> tuple[int, int, int]:
    return (
        candidate.score,
        1 if candidate.aanbod_url_quality == "valid" else 0,
        int(candidate.confidence * 100),
    )


def _merge_source_origin(left: str, right: str) -> str:
    ordered: list[str] = []
    for item in (left, right):
        for part in item.split("+"):
            normalized = part.strip()
            if normalized and normalized not in ordered:
                ordered.append(normalized)
    return "+".join(ordered)


def _merge_candidates(preferred: SourceCandidate, other: SourceCandidate) -> SourceCandidate:
    preferred.source_origin = _merge_source_origin(preferred.source_origin, other.source_origin)
    preferred.source_adapter = preferred.source_origin

    if not preferred.notes and other.notes:
        preferred.notes = other.notes
    elif preferred.notes and other.notes and other.notes not in preferred.notes:
        preferred.notes = f"{preferred.notes} | {other.notes}"

    for field_name in (
        "osm_type",
        "osm_id",
        "osm_website",
        "osm_contact_website",
        "osm_city",
        "osm_postcode",
        "osm_phone",
        "osm_contact_phone",
        "osm_email",
        "osm_contact_email",
        "osm_lat",
        "osm_lon",
        "rejection_reason",
    ):
        if not getattr(preferred, field_name) and getattr(other, field_name):
            setattr(preferred, field_name, getattr(other, field_name))

    if other.review_reason and other.review_reason not in preferred.review_reason:
        preferred.review_reason = "; ".join(part for part in (preferred.review_reason, other.review_reason) if part)

    return preferred


def dedupe_candidates(candidates: list[SourceCandidate]) -> list[SourceCandidate]:
    deduped: dict[tuple[str, str], SourceCandidate] = {}

    for candidate in candidates:
        gemeente_key = candidate.gemeente.strip().lower()
        root_domain_key = candidate.root_domain.strip().lower()
        office_key = normalize_office_name(candidate.office_name)
        key = (root_domain_key, gemeente_key) if root_domain_key else (office_key, gemeente_key)

        current = deduped.get(key)
        if current is None:
            deduped[key] = candidate
            continue

        if _candidate_rank(candidate) > _candidate_rank(current):
            deduped[key] = _merge_candidates(candidate, current)
        else:
            deduped[key] = _merge_candidates(current, candidate)

    return sorted(
        deduped.values(),
        key=lambda item: (item.gemeente.lower(), item.root_domain.lower(), normalize_office_name(item.office_name)),
    )
