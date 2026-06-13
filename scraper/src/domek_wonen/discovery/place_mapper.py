from __future__ import annotations

CURRENT_GEMEENTES = {
    "Alphen-Chaam",
    "Altena",
    "Asten",
    "Baarle-Nassau",
    "Bergeijk",
    "Bergen op Zoom",
    "Bernheze",
    "Best",
    "Bladel",
    "Boekel",
    "Boxtel",
    "Breda",
    "Cranendonck",
    "Deurne",
    "Dongen",
    "Drimmelen",
    "Eersel",
    "Eindhoven",
    "Etten-Leur",
    "Geertruidenberg",
    "Geldrop-Mierlo",
    "Gemert-Bakel",
    "Gilze en Rijen",
    "Goirle",
    "Halderberge",
    "Heeze-Leende",
    "Helmond",
    "Heusden",
    "Hilvarenbeek",
    "Laarbeek",
    "Land van Cuijk",
    "Loon op Zand",
    "Maashorst",
    "Meierijstad",
    "Moerdijk",
    "Nuenen, Gerwen en Nederwetten",
    "Oirschot",
    "Oisterwijk",
    "Oosterhout",
    "Oss",
    "Reusel-De Mierden",
    "Roosendaal",
    "Rucphen",
    "Sint-Michielsgestel",
    "Someren",
    "Son en Breugel",
    "Steenbergen",
    "Tilburg",
    "Valkenswaard",
    "Veldhoven",
    "Vught",
    "Waalre",
    "Waalwijk",
    "Woensdrecht",
    "Zundert",
    "'s-Hertogenbosch",
}

LOWERCASE_WORDS = {"aan", "de", "den", "der", "en", "het", "in", "of", "op", "te", "ten", "ter", "van"}

EXPLICIT_MAPPINGS = {
    "alphen chaam": ("Alphen-Chaam", "Alphen-Chaam", "alias"),
    "baarle nassau": ("Baarle-Nassau", "Baarle-Nassau", "alias"),
    "bergen op zoom": ("Bergen op Zoom", "Bergen op Zoom", "alias"),
    "berkel enschot": ("Berkel-Enschot", "Tilburg", "locality_to_gemeente"),
    "berlicum": ("Berlicum", "Sint-Michielsgestel", "locality_to_gemeente"),
    "bavel": ("Bavel", "Breda", "locality_to_gemeente"),
    "boxmeer": ("Boxmeer", "Land van Cuijk", "former_gemeente"),
    "cuijk": ("Cuijk", "Land van Cuijk", "former_gemeente"),
    "den bosch": ("'s-Hertogenbosch", "'s-Hertogenbosch", "alias"),
    "etten leur": ("Etten-Leur", "Etten-Leur", "alias"),
    "geldrop mierlo": ("Geldrop-Mierlo", "Geldrop-Mierlo", "alias"),
    "gemert": ("Gemert", "Gemert-Bakel", "locality_to_gemeente"),
    "gemert bakel": ("Gemert-Bakel", "Gemert-Bakel", "alias"),
    "gilze en rijen": ("Gilze en Rijen", "Gilze en Rijen", "alias"),
    "heeze leende": ("Heeze-Leende", "Heeze-Leende", "alias"),
    "land van cuijk": ("Land van Cuijk", "Land van Cuijk", "alias"),
    "landerd": ("Maashorst", "Maashorst", "former_gemeente"),
    "loon op zand": ("Loon op Zand", "Loon op Zand", "alias"),
    "mierlo": ("Mierlo", "Geldrop-Mierlo", "locality_to_gemeente"),
    "nuenen": ("Nuenen", "Nuenen, Gerwen en Nederwetten", "locality_to_gemeente"),
    "nuenen gerwen en nederwetten": (
        "Nuenen, Gerwen en Nederwetten",
        "Nuenen, Gerwen en Nederwetten",
        "alias",
    ),
    "prinsenbeek": ("Prinsenbeek", "Breda", "locality_to_gemeente"),
    "reusel de mierden": ("Reusel-De Mierden", "Reusel-De Mierden", "alias"),
    "rijen": ("Rijen", "Gilze en Rijen", "locality_to_gemeente"),
    "rosmalen": ("Rosmalen", "'s-Hertogenbosch", "locality_to_gemeente"),
    "s hertogenbosch": ("'s-Hertogenbosch", "'s-Hertogenbosch", "alias"),
    "s-hertogenbosch": ("'s-Hertogenbosch", "'s-Hertogenbosch", "alias"),
    "schijndel": ("Schijndel", "Meierijstad", "former_gemeente"),
    "sint michielsgestel": ("Sint-Michielsgestel", "Sint-Michielsgestel", "alias"),
    "son en breugel": ("Son en Breugel", "Son en Breugel", "alias"),
    "uden": ("Uden", "Maashorst", "former_gemeente"),
    "udenhout": ("Udenhout", "Tilburg", "locality_to_gemeente"),
}

STATUS_REVIEW_REASONS = {
    "locality_to_gemeente": "Mapped locality to official gemeente.",
    "former_gemeente": "Mapped former municipality to current gemeente.",
    "alias": "Normalized alias to canonical gemeente name.",
    "current_gemeente": "Matched a current gemeente.",
}


def clean_spaces(value: str) -> str:
    return " ".join((value or "").strip().split())


def lookup_key(value: str) -> str:
    cleaned = clean_spaces(value).lower()
    for token in ("'", "-", ",", ".", "/"):
        cleaned = cleaned.replace(token, " ")
    return " ".join(cleaned.split())


def title_token(token: str) -> str:
    if not token:
        return token
    if token in LOWERCASE_WORDS:
        return token
    if token.startswith("'s"):
        return "'s" + token[2:].capitalize()
    return token.capitalize()


def title_case_place(value: str) -> str:
    words = [title_token(token) for token in clean_spaces(value).lower().split(" ")]
    return " ".join(words)


CANONICAL_BY_LOOKUP = {lookup_key(name): name for name in CURRENT_GEMEENTES}


def normalize_overpass_city(raw_city: str) -> dict[str, str]:
    raw_place = clean_spaces(raw_city)
    if not raw_place:
        return {
            "raw_place": "",
            "normalized_place": "(unknown)",
            "gemeente": "(unknown)",
            "place_status": "needs_review",
            "review_reason": "Missing addr:city in Overpass tags.",
        }

    key = lookup_key(raw_place)
    explicit = EXPLICIT_MAPPINGS.get(key)
    if explicit:
        normalized_place, gemeente, place_status = explicit
        return {
            "raw_place": raw_place,
            "normalized_place": normalized_place,
            "gemeente": gemeente,
            "place_status": place_status,
            "review_reason": "",
        }

    canonical = CANONICAL_BY_LOOKUP.get(key)
    if canonical:
        return {
            "raw_place": raw_place,
            "normalized_place": canonical,
            "gemeente": canonical,
            "place_status": "current_gemeente",
            "review_reason": "",
        }

    return {
        "raw_place": raw_place,
        "normalized_place": "(unknown)",
        "gemeente": "(unknown)",
        "place_status": "needs_review",
        "review_reason": (
            f"Unmapped Overpass place '{title_case_place(raw_place)}'; gemeente could not be normalized."
        ),
    }
