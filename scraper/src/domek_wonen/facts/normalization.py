from __future__ import annotations

import re
from typing import Any


_NUMBER_PATTERN = re.compile(r"\d[\d\., ]*")
_WHITESPACE_PATTERN = re.compile(r"\s+")

_PROPERTY_TYPE_MAPPING = {
    "appartement": "appartement",
    "tussenwoning": "tussenwoning",
    "hoekwoning": "hoekwoning",
    "vrijstaande woning": "vrijstaande_woning",
    "vrijstaand": "vrijstaande_woning",
    "twee onder een kap": "twee_onder_een_kap",
    "twee-onder-een-kap": "twee_onder_een_kap",
    "2 onder 1 kap": "twee_onder_een_kap",
    "herenhuis": "herenhuis",
    "benedenwoning": "benedenwoning",
    "bovenwoning": "bovenwoning",
    "maisonette": "maisonette",
    "bungalow": "bungalow",
    "studio": "studio",
    "bouwgrond": "bouwgrond",
    "woonhuis": "woonhuis",
    "eengezinswoning": "woonhuis",
    "woning": "woonhuis",
    "garage": "garage",
}

_ENERGY_LABELS = ("A++++", "A+++", "A++", "A+", "A", "B", "C", "D", "E", "F", "G")
_DESCRIPTION_BUCKETS = frozenset({"none", "short", "medium", "long"})


def normalize_price(value: object) -> int | None:
    return _first_int(value)


def normalize_area_m2(value: object) -> int | None:
    return _first_int(value)


def normalize_count(value: object) -> int | None:
    return _first_int(value)


def normalize_energy_label(value: object) -> str | None:
    text = _clean_text(value).upper().replace(" ", "")
    if not text:
        return None
    for label in _ENERGY_LABELS:
        if label in text:
            return label
    return None


def normalize_property_type(value: object) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    normalized = _normalize_token_text(text)
    if normalized in {"unknown", "onbekend", "nvt", "n/a", "none", "null"}:
        return "unknown"
    if normalized in _PROPERTY_TYPE_MAPPING:
        return _PROPERTY_TYPE_MAPPING[normalized]
    compact = normalized.replace("-", " ")
    return _PROPERTY_TYPE_MAPPING.get(compact, "unknown")


def normalize_boolean_signal(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    text = _clean_text(value)
    if not text:
        return None
    if text in {"true", "1", "yes", "ja", "aanwezig", "source_available", "beschikbaar"}:
        return True
    if text in {"false", "0", "no", "nee", "niet aanwezig", "geen", "none"}:
        return False
    return None


def normalize_vve_monthly_cost(value: object) -> int | None:
    return _first_int(value)


def normalize_cv_ketel_ownership(value: object) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    if "eigendom" in text or "owned" in text:
        return "eigendom"
    if "huur" in text or "gehuurd" in text:
        return "huur"
    if "lease" in text:
        return "lease"
    if text in {"unknown", "onbekend"}:
        return "unknown"
    return "unknown"


def normalize_eigendomssituatie(value: object) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    if "volle eigendom" in text:
        return "volle_eigendom"
    if "eigen grond" in text:
        return "eigen_grond"
    if "erfpacht" in text:
        return "erfpacht"
    if text in {"unknown", "onbekend"}:
        return "unknown"
    return "unknown"


def normalize_description_length_bucket(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, int):
        if value <= 0:
            return "none"
        if value < 250:
            return "short"
        if value < 1000:
            return "medium"
        return "long"
    text = _clean_text(value)
    if not text:
        return None
    if text in _DESCRIPTION_BUCKETS:
        return text
    return None


def _first_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = _clean_text(value)
    if not text:
        return None
    match = _NUMBER_PATTERN.search(text)
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(0))
    return int(digits) if digits else None


def _clean_text(value: Any) -> str:
    return _WHITESPACE_PATTERN.sub(" ", str(value or "")).strip().casefold()


def _normalize_token_text(value: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", value.replace("_", " ").strip().casefold())
