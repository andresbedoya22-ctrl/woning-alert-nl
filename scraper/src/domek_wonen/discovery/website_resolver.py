from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from .models import SourceCandidate

NAME_NOISE_TOKENS = {
    "bv",
    "b v",
    "b.v",
    "b.v.",
    "makelaar",
    "makelaars",
    "makelaardij",
    "vastgoed",
}


@dataclass(slots=True)
class WebsiteResolverOutput:
    resolved_candidates: list[SourceCandidate]
    unresolved_candidates: list[SourceCandidate]
    manual_review_rows: list[dict[str, str]]


def normalize_office_name(value: str) -> str:
    cleaned = (value or "").lower()
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    parts = [part for part in cleaned.split() if part not in NAME_NOISE_TOKENS]
    return " ".join(parts)


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(a=left, b=right).ratio()


def _suggested_domains(candidate: SourceCandidate, seed_candidates: list[SourceCandidate]) -> list[str]:
    normalized = normalize_office_name(candidate.office_name)
    ranked: list[tuple[float, str]] = []
    for seed in seed_candidates:
        if not seed.root_domain:
            continue
        score = _similarity(normalized, normalize_office_name(seed.office_name))
        if score >= 0.6:
            ranked.append((score, seed.root_domain))
    ordered: list[str] = []
    for _, domain in sorted(ranked, key=lambda item: item[0], reverse=True):
        if domain not in ordered:
            ordered.append(domain)
        if len(ordered) >= 3:
            break
    return ordered


def resolve_websites(
    candidates: list[SourceCandidate],
    *,
    seed_candidates: list[SourceCandidate],
) -> WebsiteResolverOutput:
    resolved: list[SourceCandidate] = []
    unresolved: list[SourceCandidate] = []
    manual_rows: list[dict[str, str]] = []

    for candidate in candidates:
        normalized_candidate_name = normalize_office_name(candidate.office_name)
        exact_match: SourceCandidate | None = None
        best_match: SourceCandidate | None = None
        best_score = 0.0

        same_gemeente = [seed for seed in seed_candidates if seed.gemeente and seed.gemeente == candidate.gemeente and seed.website]
        pool = same_gemeente or [seed for seed in seed_candidates if seed.website]

        for seed in pool:
            normalized_seed_name = normalize_office_name(seed.office_name)
            if normalized_candidate_name and normalized_candidate_name == normalized_seed_name:
                exact_match = seed
                best_match = seed
                best_score = 1.0
                break
            similarity = _similarity(normalized_candidate_name, normalized_seed_name)
            if similarity > best_score:
                best_score = similarity
                best_match = seed

        if exact_match is not None or best_score >= 0.88:
            match = best_match
            if match is not None:
                candidate.website = match.website
                candidate.root_domain = match.root_domain
                candidate.website_resolution_status = "resolved_seed_match"
                candidate.review_reason = "; ".join(
                    part for part in (candidate.review_reason, f"website resolved from seed ({best_score:.2f})") if part
                )
                resolved.append(candidate)
                continue

        candidate.website_resolution_status = "needs_manual_review"
        candidate.review_reason = "; ".join(
            part for part in (candidate.review_reason, "website unresolved after seed fuzzy match") if part
        )
        unresolved.append(candidate)
        manual_rows.append(
            {
                "office_name": candidate.office_name,
                "gemeente": candidate.gemeente,
                "plaats": candidate.plaats,
                "source_origin": candidate.source_origin,
                "raw_place": candidate.raw_place,
                "normalized_place": candidate.normalized_place,
                "phone": candidate.osm_phone or candidate.osm_contact_phone,
                "email": candidate.osm_email or candidate.osm_contact_email,
                "lat": candidate.osm_lat,
                "lon": candidate.osm_lon,
                "reason": "missing_website_unresolved",
                "suggested_domains": ",".join(_suggested_domains(candidate, seed_candidates)),
                "notes": candidate.notes,
            }
        )

    return WebsiteResolverOutput(
        resolved_candidates=resolved,
        unresolved_candidates=unresolved,
        manual_review_rows=manual_rows,
    )
