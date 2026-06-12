from __future__ import annotations

from pathlib import Path


DISCOVERY_BASE_DIR = Path(__file__).resolve().parents[4]
DEFAULT_SEED_PATH = (
    DISCOVERY_BASE_DIR / "data" / "discovery" / "processed" / "sources_seed_with_gemeente.csv"
)
DEFAULT_GEMEENTEN_REFERENCE_PATH = (
    DISCOVERY_BASE_DIR / "data" / "discovery" / "reference" / "noord_brabant_gemeenten_expected.csv"
)

QUERY_TEMPLATES = (
    "makelaar koopwoningen {gemeente}",
    "woningaanbod makelaar {gemeente}",
    "NVM makelaar {gemeente}",
    "Vastgoed Nederland makelaar {gemeente}",
    "VBO makelaar {gemeente}",
    "site:.nl makelaar {gemeente} koopwoningen",
    "site:.nl {gemeente} makelaardij aanbod",
    "site:.nl {gemeente} makelaar wonen",
)

VALID_AANBOD_SIGNALS = (
    "aanbod",
    "woningaanbod",
    "koopwoningen",
    "koop",
    "wonen",
    "woningen",
    "huizen",
    "objecten",
)

EXCLUDED_AANBOD_TOKENS = (
    "verkoopadvies",
    "gratis-verkoopadvies",
    "waardebepaling",
    "taxatie",
    "contact",
    "over-ons",
    "diensten",
    "hypotheek",
    "blog",
    "nieuws",
    "privacy",
    "reviews",
    "aankoopmakelaar",
    "verkoopmakelaar",
)

COMMON_AANBOD_PATHS = (
    "/aanbod",
    "/woningaanbod",
    "/koopwoningen",
    "/koop",
    "/wonen",
    "/huizen-aanbod",
    "/objecten",
)

MAKELAAR_SIGNALS = (
    "makelaar",
    "makelaardij",
    "real estate",
    "woning",
    "wonen",
    "nvm",
    "vbo",
    "vastgoed nederland",
)

COMMERCIAL_ONLY_TOKENS = (
    "bedrijfshuisvesting",
    "taxatie",
)
