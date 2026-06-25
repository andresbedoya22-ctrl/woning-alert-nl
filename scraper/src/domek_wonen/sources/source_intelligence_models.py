from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
import re
from urllib.parse import urlsplit


TRUTHY_VALUES = {"1", "true", "yes", "y", "ja"}
FALSY_VALUES = {"0", "false", "no", "n", "nee", "none", "null", "nan", ""}


@dataclass(slots=True)
class SourceIntelligenceRecord:
    source_id: str = ""
    source_domain: str = ""
    source_name: str = ""
    organization_type: str = ""
    membership_hint: str = ""
    province: str = ""
    gemeente: str = ""
    city_scope: str = ""
    homepage_url: str = ""
    aanbod_url: str = ""
    aanbod_url_status: str = ""
    access_status: str = ""
    robots_status: str = ""
    terms_status: str = ""
    blocking_status: str = ""
    has_login: bool = False
    has_captcha: bool = False
    has_403: bool = False
    has_sitemap: bool = False
    has_wp_json: bool = False
    has_json_ld: bool = False
    has_visible_cards: bool = False
    has_iframe: bool = False
    iframe_domain: str = ""
    is_funda_dependent: bool = False
    is_pararius_dependent: bool = False
    technology_signals: str = ""
    detected_platform: str = ""
    delivery_mode: str = ""
    delivery_mode_confidence: float = 0.0
    parser_family_candidate: str = ""
    config_required: bool = False
    config_path: str = ""
    estimated_listing_count: int = 0
    koop_signal: bool = False
    huur_signal: bool = False
    commercial_signal: bool = False
    project_signal: bool = False
    quality_score: int = 0
    recommended_action: str = ""
    priority_score: int = 0
    evidence: str = ""
    last_reviewed_at: str = ""
    notes: str = ""


def parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    normalized = normalize_text(value)
    if normalized in TRUTHY_VALUES:
        return True
    if normalized in FALSY_VALUES:
        return False
    return False


def parse_int(value: object, default: int = 0) -> int:
    text = normalize_text(value)
    if not text:
        return default
    try:
        return int(float(text))
    except ValueError:
        return default


def parse_float(value: object, default: float = 0.0) -> float:
    text = normalize_text(value)
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_key(value: object) -> str:
    return normalize_text(value).lower()


def normalize_domain(value: object) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    candidate = text
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    split = urlsplit(candidate)
    host = (split.netloc or split.path).strip().lower()
    if "@" in host:
        host = host.rsplit("@", 1)[-1]
    if ":" in host:
        host = host.split(":", 1)[0]
    if host.startswith("www."):
        host = host[4:]
    return host.strip().strip("/")


def make_source_id(
    source_domain: str,
    gemeente: str,
    source_name: str,
    homepage_url: str,
    aanbod_url: str,
) -> str:
    base_slug = slugify(source_domain or source_name or gemeente or "source")
    scope_slug = slugify(gemeente) or "na"
    fingerprint = sha1(
        "|".join(
            [
                normalize_key(source_domain),
                normalize_key(gemeente),
                normalize_key(source_name),
                normalize_key(homepage_url),
                normalize_key(aanbod_url),
            ]
        ).encode("utf-8")
    ).hexdigest()[:10]
    return f"{base_slug}__{scope_slug}__{fingerprint}"


def slugify(value: object) -> str:
    text = normalize_key(value)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")

