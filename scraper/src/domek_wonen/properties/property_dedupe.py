from __future__ import annotations

from .models import PropertyCandidate


def normalize_property_url(value: str) -> str:
    url = (value or "").strip()
    if not url:
        return ""
    url = url.rstrip("/")
    if url.startswith("http://"):
        url = "https://" + url[len("http://") :]
    return url.lower()


def fallback_key(candidate: PropertyCandidate) -> str:
    return " | ".join(
        [
            (candidate.address_raw or "").strip().lower(),
            (candidate.city_raw or "").strip().lower(),
            (candidate.price_raw or "").strip().lower(),
        ]
    )


class PropertyDedupe:
    def dedupe(self, candidates: list[PropertyCandidate]) -> list[PropertyCandidate]:
        kept: dict[str, PropertyCandidate] = {}
        order: list[str] = []
        for candidate in candidates:
            key = normalize_property_url(candidate.property_url) or fallback_key(candidate)
            if not key.strip(" |"):
                key = f"{candidate.source_id}|{len(order)}"
            existing = kept.get(key)
            if existing is None:
                kept[key] = candidate
                order.append(key)
                continue
            kept[key] = self._pick_better(existing, candidate)
        return [kept[key] for key in order]

    def _pick_better(self, left: PropertyCandidate, right: PropertyCandidate) -> PropertyCandidate:
        left_score = self._score(left)
        right_score = self._score(right)
        return right if right_score > left_score else left

    def _score(self, candidate: PropertyCandidate) -> tuple[float, int]:
        populated = sum(
            1
            for value in (
                candidate.title,
                candidate.address_raw,
                candidate.city_raw,
                candidate.price_raw,
                candidate.status_raw,
                candidate.living_area_raw,
                candidate.plot_area_raw,
                candidate.rooms_raw,
                candidate.image_url,
            )
            if value
        )
        return (candidate.extraction_confidence, populated)
