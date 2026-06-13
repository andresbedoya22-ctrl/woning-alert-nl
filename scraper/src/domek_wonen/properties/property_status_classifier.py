from __future__ import annotations

import re


class PropertyStatusClassifier:
    def classify(self, *parts: str) -> str:
        haystack = " ".join(part for part in parts if part).strip().lower()
        if not haystack:
            return "unknown"
        if "onder bod" in haystack:
            return "onder_bod"
        if any(token in haystack for token in ("verkocht onder voorbehoud", "verkocht o.v.", "verkocht ov")):
            return "verkocht_ov"
        if any(token in haystack for token in ("verdwenen", "ingetrokken", "niet meer beschikbaar", "withdrawn")):
            return "verdwenen"
        if "verkocht" in haystack:
            return "verkocht"
        if any(token in haystack for token in ("beschikbaar", "te koop", "vraagprijs", "prijs op aanvraag", "k.k.")):
            return "beschikbaar"
        return "unknown"


def parse_price_eur(price_raw: str) -> str:
    digits = re.sub(r"[^\d]", "", price_raw or "")
    if not digits:
        return ""
    return str(int(digits))
