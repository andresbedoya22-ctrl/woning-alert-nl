from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

from .config import COMMON_AANBOD_PATHS, EXCLUDED_AANBOD_TOKENS, VALID_AANBOD_SIGNALS


@dataclass(slots=True)
class AanbodClassification:
    status: str
    reason: str
    url: str = ""


def _normalize_url(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    return raw.rstrip("/")


def _haystack(url: str) -> str:
    parsed = urlsplit(url)
    return f"{parsed.netloc}{parsed.path}".lower()


def classify_aanbod_url(url: str | None) -> AanbodClassification:
    normalized = _normalize_url(url)
    if not normalized:
        return AanbodClassification(status="missing", reason="missing aanbod_url")

    haystack = _haystack(normalized)
    if "bedrijfshuisvesting" in haystack and not any(token in haystack for token in ("woning", "koop", "wonen")):
        return AanbodClassification(status="rejected", reason="commercial-only token 'bedrijfshuisvesting'", url=normalized)

    matched_excluded = [token for token in EXCLUDED_AANBOD_TOKENS if token in haystack]
    if matched_excluded:
        status = "rejected" if "contact" in matched_excluded or "privacy" in matched_excluded else "suspect"
        return AanbodClassification(
            status=status,
            reason=f"contains excluded token '{matched_excluded[0]}'",
            url=normalized,
        )

    if any(token in haystack for token in VALID_AANBOD_SIGNALS):
        return AanbodClassification(status="valid", reason="contains listing signal", url=normalized)

    return AanbodClassification(status="suspect", reason="missing listing signal", url=normalized)


def suggest_common_aanbod_paths(website: str | None) -> list[str]:
    normalized = _normalize_url(website)
    if not normalized:
        return []
    return [urljoin(f"{normalized}/", path.lstrip("/")) for path in COMMON_AANBOD_PATHS]
