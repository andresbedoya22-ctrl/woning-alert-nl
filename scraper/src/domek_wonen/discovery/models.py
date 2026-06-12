from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class SourceCandidate:
    office_name: str
    website: str = ""
    root_domain: str = ""
    gemeente: str = ""
    plaats: str = ""
    provincie: str = ""
    aanbod_url: str = ""
    aanbod_url_quality: str = "missing"
    confidence: float = 0.0
    needs_review: bool = False
    source_adapter: str = "seed"
    score: int = 0
    status: str = "missing"
    review_reason: str = ""
    evidence: list[str] = field(default_factory=list)


@dataclass(slots=True)
class GeneratedQuery:
    gemeente: str
    query: str
    template: str
    provincie: str = ""


@dataclass(slots=True)
class DiscoveryResult:
    candidate: SourceCandidate
    score: int
    status: str
    reasons: list[str] = field(default_factory=list)
