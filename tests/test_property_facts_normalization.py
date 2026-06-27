from pathlib import Path
import sys


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.facts.normalization import (
    normalize_area_m2,
    normalize_count,
    normalize_cv_ketel_ownership,
    normalize_description_length_bucket,
    normalize_eigendomssituatie,
    normalize_energy_label,
    normalize_price,
    normalize_property_type,
    normalize_vve_monthly_cost,
)


def test_normalize_price_from_display_text() -> None:
    assert normalize_price("EUR 425.000 k.k.") == 425000


def test_normalize_area_m2_from_display_text() -> None:
    assert normalize_area_m2("112 m2") == 112


def test_normalize_count_from_bedroom_text() -> None:
    assert normalize_count("3 slaapkamers") == 3


def test_normalize_energy_label() -> None:
    assert normalize_energy_label("A++") == "A++"


def test_normalize_property_type_known_values() -> None:
    assert normalize_property_type("Tussenwoning") == "tussenwoning"
    assert normalize_property_type("Vrijstaande woning") == "vrijstaande_woning"


def test_normalize_vve_monthly_cost() -> None:
    assert normalize_vve_monthly_cost("EUR 125 per maand") == 125


def test_normalize_cv_ketel_ownership() -> None:
    assert normalize_cv_ketel_ownership("CV-ketel eigendom") == "eigendom"
    assert normalize_cv_ketel_ownership("huurketel") == "huur"


def test_normalize_eigendomssituatie() -> None:
    assert normalize_eigendomssituatie("Volle eigendom") == "volle_eigendom"
    assert normalize_eigendomssituatie("eigen grond") == "eigen_grond"


def test_unknown_or_empty_values_are_consistent() -> None:
    assert normalize_price("") is None
    assert normalize_energy_label("") is None
    assert normalize_property_type("mystery type") == "unknown"
    assert normalize_description_length_bucket("") is None
