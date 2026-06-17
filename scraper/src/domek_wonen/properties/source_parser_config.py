from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


REQUIRED_CONFIG_FIELDS = [
    "source_domain",
    "parser_family",
    "listing_url",
    "card_selector",
    "detail_url_selector",
    "address_selector",
    "price_selector",
    "status_selector",
    "city_selector",
    "living_area_selector",
    "rooms_selector",
    "image_selector",
    "pagination_strategy",
    "detail_enrichment_required",
    "known_noise_selectors",
    "status_mapping",
    "price_patterns",
    "qa_expectations",
]

ALLOWED_PARSER_FAMILIES = {"html_static_cards", "wordpress_cards"}
ALLOWED_PAGINATION_STRATEGIES = {"none", "next_link", "page_param", "load_more"}


@dataclass(frozen=True, slots=True)
class ParserConfigValidationResult:
    ok: bool
    errors: list[str]


def load_json_file(path: Path) -> dict | list:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_source_parser_config(config: dict) -> ParserConfigValidationResult:
    errors: list[str] = []
    if not isinstance(config, dict):
        return ParserConfigValidationResult(ok=False, errors=["config must be a JSON object"])

    for field_name in REQUIRED_CONFIG_FIELDS:
        if field_name not in config:
            errors.append(f"missing required field: {field_name}")

    if errors:
        return ParserConfigValidationResult(ok=False, errors=errors)

    parser_family = config.get("parser_family")
    if parser_family not in ALLOWED_PARSER_FAMILIES:
        errors.append(
            "parser_family must be one of: " + ", ".join(sorted(ALLOWED_PARSER_FAMILIES))
        )

    pagination_strategy = config.get("pagination_strategy")
    if pagination_strategy not in ALLOWED_PAGINATION_STRATEGIES:
        errors.append(
            "pagination_strategy must be one of: " + ", ".join(sorted(ALLOWED_PAGINATION_STRATEGIES))
        )

    for field_name in [
        "source_domain",
        "listing_url",
        "card_selector",
        "detail_url_selector",
        "address_selector",
        "price_selector",
        "status_selector",
        "city_selector",
        "living_area_selector",
        "rooms_selector",
        "image_selector",
    ]:
        if not isinstance(config.get(field_name), str) or not config.get(field_name).strip():
            errors.append(f"{field_name} must be a non-empty string")

    if not isinstance(config.get("detail_enrichment_required"), bool):
        errors.append("detail_enrichment_required must be a boolean")

    for field_name in ["known_noise_selectors", "price_patterns"]:
        value = config.get(field_name)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            errors.append(f"{field_name} must be a list of strings")

    status_mapping = config.get("status_mapping")
    if not isinstance(status_mapping, dict) or not status_mapping:
        errors.append("status_mapping must be a non-empty object")
    else:
        for key, value in status_mapping.items():
            if not isinstance(key, str) or not key.strip() or not isinstance(value, str) or not value.strip():
                errors.append("status_mapping must contain non-empty string keys and values")
                break

    qa_expectations = config.get("qa_expectations")
    if not isinstance(qa_expectations, dict):
        errors.append("qa_expectations must be an object")
    else:
        for field_name in ["min_card_count", "requires_address", "requires_price"]:
            if field_name not in qa_expectations:
                errors.append(f"qa_expectations missing required field: {field_name}")
        if "min_card_count" in qa_expectations and not isinstance(qa_expectations.get("min_card_count"), int):
            errors.append("qa_expectations.min_card_count must be an integer")
        for field_name in ["requires_address", "requires_price"]:
            if field_name in qa_expectations and not isinstance(qa_expectations.get(field_name), bool):
                errors.append(f"qa_expectations.{field_name} must be a boolean")

    return ParserConfigValidationResult(ok=not errors, errors=errors)


def validate_source_parser_config_file(path: Path) -> ParserConfigValidationResult:
    return validate_source_parser_config(load_json_file(path))
