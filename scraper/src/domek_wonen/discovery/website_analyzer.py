from __future__ import annotations

from dataclasses import dataclass, field

from .models import SourceCandidate


WEBSITE_SIGNAL_TOKENS = (
    "makelaar",
    "makelaardij",
    "vastgoed",
    "wonen",
    "woningen",
    "aanbod",
    "koop",
    "nvm",
    "era",
)


@dataclass(slots=True)
class WebsiteAnalysis:
    website_exists: bool
    makelaar_signals: list[str] = field(default_factory=list)
    signal_count: int = 0


def analyze_candidate_website(candidate: SourceCandidate) -> WebsiteAnalysis:
    haystack = " ".join(
        value.lower()
        for value in (
            candidate.office_name,
            candidate.website,
            candidate.root_domain,
            candidate.aanbod_url,
        )
        if value
    )
    matched = [token for token in WEBSITE_SIGNAL_TOKENS if token in haystack]
    return WebsiteAnalysis(
        website_exists=bool(candidate.website),
        makelaar_signals=matched,
        signal_count=len(matched),
    )
