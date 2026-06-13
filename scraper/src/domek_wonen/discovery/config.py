from __future__ import annotations

from pathlib import Path


DISCOVERY_BASE_DIR = Path(__file__).resolve().parents[4]
DEFAULT_SEED_PATH = (
    DISCOVERY_BASE_DIR / "data" / "discovery" / "processed" / "sources_seed_with_gemeente.csv"
)
DEFAULT_GEMEENTEN_REFERENCE_PATH = (
    DISCOVERY_BASE_DIR / "data" / "discovery" / "reference" / "noord_brabant_gemeenten_expected.csv"
)
DEFAULT_AGGREGATOR_LEGAL_REGISTRY_PATH = (
    DISCOVERY_BASE_DIR / "data" / "discovery" / "reference" / "aggregator_legal_registry.csv"
)
DISCOVERY_CACHE_DIR = DISCOVERY_BASE_DIR / "data" / "discovery" / "cache"

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
    "te-koop",
)

EXCLUDED_AANBOD_TOKENS = (
    "verkoopadvies",
    "gratis-verkoopadvies",
    "waardebepaling",
    "taxatie",
    "taxaties",
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
    "vacatures",
    "team",
    "about",
)

COMMON_AANBOD_PATHS = (
    "/aanbod",
    "/woningaanbod",
    "/koopwoningen",
    "/koop",
    "/wonen",
    "/woningen",
    "/huizen",
    "/objecten",
    "/aanbod/koopwoningen",
    "/aanbod/woningaanbod",
    "/aanbod/koop",
    "/nl/aanbod",
    "/nl/koopwoningen",
    "/nl/woningaanbod",
    "/huizen-te-koop",
    "/woningen-te-koop",
    "/koopaanbod",
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

LIVE_AANBOD_USER_AGENT = "DomekWonenAanbodFinder/2.0 (+https://example.invalid/bot; contact=ops@domek.invalid)"
LIVE_AANBOD_TIMEOUT_SECONDS = 8.0
LIVE_AANBOD_DELAY_SECONDS = 0.35
LIVE_AANBOD_MAX_SITEMAP_URLS = 40

PAGE_LISTING_SIGNALS = (
    "prijs",
    "vraagprijs",
    "k.k.",
    "kosten koper",
    "koop",
    "verkocht",
    "beschikbaar",
    "onder bod",
    "woonoppervlakte",
    "perceel",
    "kamers",
    "slaapkamers",
    "adres",
    "postcode",
    "woning",
    "appartement",
    "vrijstaand",
    "tussenwoning",
)
