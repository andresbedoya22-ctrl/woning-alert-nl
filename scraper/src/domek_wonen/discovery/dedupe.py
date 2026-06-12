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


def dedupe_candidates(candidates: list[SourceCandidate]) -> list[SourceCandidate]:
    deduped: dict[tuple[str, str], SourceCandidate] = {}

    for candidate in candidates:
        gemeente_key = candidate.gemeente.strip().lower()
        root_domain_key = candidate.root_domain.strip().lower()
        office_key = normalize_office_name(candidate.office_name)
        key = (root_domain_key, gemeente_key) if root_domain_key else (office_key, gemeente_key)

        current = deduped.get(key)
        if current is None or _candidate_rank(candidate) > _candidate_rank(current):
            deduped[key] = candidate

    return sorted(
        deduped.values(),
        key=lambda item: (item.gemeente.lower(), item.root_domain.lower(), normalize_office_name(item.office_name)),
    )
