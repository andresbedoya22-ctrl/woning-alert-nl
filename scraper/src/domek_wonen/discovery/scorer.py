from __future__ import annotations

from .aanbod_finder import classify_aanbod_url
from .config import COMMERCIAL_ONLY_TOKENS, EXCLUDED_AANBOD_TOKENS, MAKELAAR_SIGNALS, VALID_AANBOD_SIGNALS
from .models import DiscoveryResult, SourceCandidate


def score_candidate(candidate: SourceCandidate) -> DiscoveryResult:
    score = 0
    reasons: list[str] = []

    website_text = " ".join(
        part
        for part in (
            candidate.website.lower(),
            candidate.root_domain.lower(),
            candidate.office_name.lower(),
        )
        if part
    )
    aanbod_classification = classify_aanbod_url(candidate.aanbod_url)
    aanbod_text = (candidate.aanbod_url or "").lower()

    if candidate.website:
        score += 20
        reasons.append("website exists")

    if any(token in website_text for token in MAKELAAR_SIGNALS):
        score += 20
        reasons.append("makelaar signal")

    if aanbod_classification.status == "valid":
        score += 30
        reasons.append("aanbod_url found")
    elif aanbod_classification.status == "suspect":
        reasons.append("aanbod_url suspect")

    if any(token in aanbod_text for token in VALID_AANBOD_SIGNALS):
        score += 20
        reasons.append("listing signal")

    geo_text = f"{website_text} {aanbod_text}"
    if candidate.gemeente and candidate.gemeente.lower() in geo_text:
        score += 10
        reasons.append("gemeente relevance")
    elif candidate.provincie and candidate.provincie.lower() in geo_text:
        score += 10
        reasons.append("province relevance")

    if any(token in aanbod_text for token in EXCLUDED_AANBOD_TOKENS):
        score -= 40
        reasons.append("excluded commercial page")

    if any(token in website_text or token in aanbod_text for token in COMMERCIAL_ONLY_TOKENS):
        score -= 30
        reasons.append("commercial-only focus")

    score = max(0, min(100, score))

    if score >= 70 and aanbod_classification.status == "valid":
        status = "valid"
    elif score >= 40 and candidate.website:
        status = "suspect"
    elif candidate.website:
        status = "missing"
    else:
        status = "rejected"

    return DiscoveryResult(candidate=candidate, score=score, status=status, reasons=reasons)
