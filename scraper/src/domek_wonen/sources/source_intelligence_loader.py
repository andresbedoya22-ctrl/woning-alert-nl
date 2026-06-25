from __future__ import annotations

import csv
from pathlib import Path

from .source_intelligence_models import (
    SourceIntelligenceRecord,
    make_source_id,
    normalize_domain,
    normalize_key,
    normalize_text,
    parse_bool,
    parse_float,
    parse_int,
)


def load_source_intelligence_csv(path: Path | str) -> list[SourceIntelligenceRecord]:
    csv_path = Path(path)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [build_source_intelligence_record(row) for row in rows]


def build_source_intelligence_record(row: dict[str, str]) -> SourceIntelligenceRecord:
    homepage_url = normalize_text(row.get("homepage_url") or row.get("website") or row.get("website_url"))
    aanbod_url = normalize_text(row.get("aanbod_url"))
    source_domain = normalize_domain(
        row.get("source_domain") or row.get("root_domain") or aanbod_url or homepage_url
    )
    iframe_domain = normalize_domain(row.get("iframe_domain"))
    detected_platform = normalize_text(row.get("detected_platform"))
    technology_signals = normalize_text(row.get("technology_signals"))
    evidence = normalize_text(row.get("evidence"))
    notes = normalize_text(row.get("notes"))

    record = SourceIntelligenceRecord(
        source_id=normalize_text(row.get("source_id")),
        source_domain=source_domain,
        source_name=normalize_text(row.get("source_name") or row.get("office_name") or row.get("organization_name")),
        organization_type=normalize_text(row.get("organization_type")),
        membership_hint=normalize_text(row.get("membership_hint")),
        province=normalize_text(row.get("province") or row.get("provincie")),
        gemeente=normalize_text(row.get("gemeente")),
        city_scope=normalize_text(row.get("city_scope")),
        homepage_url=homepage_url,
        aanbod_url=aanbod_url,
        aanbod_url_status=normalize_aanbod_url_status(row.get("aanbod_url_status"), aanbod_url),
        access_status=normalize_text(row.get("access_status")),
        robots_status=normalize_text(row.get("robots_status")),
        terms_status=normalize_text(row.get("terms_status")),
        blocking_status=normalize_text(row.get("blocking_status")),
        has_login=parse_bool(row.get("has_login")),
        has_captcha=parse_bool(row.get("has_captcha")),
        has_403=parse_bool(row.get("has_403")),
        has_sitemap=parse_bool(row.get("has_sitemap")),
        has_wp_json=parse_bool(row.get("has_wp_json")),
        has_json_ld=parse_bool(row.get("has_json_ld")),
        has_visible_cards=parse_bool(row.get("has_visible_cards")),
        has_iframe=parse_bool(row.get("has_iframe")),
        iframe_domain=iframe_domain,
        is_funda_dependent=parse_bool(row.get("is_funda_dependent")),
        is_pararius_dependent=parse_bool(row.get("is_pararius_dependent")),
        technology_signals=technology_signals,
        detected_platform=detected_platform,
        delivery_mode=normalize_text(row.get("delivery_mode")),
        delivery_mode_confidence=parse_float(row.get("delivery_mode_confidence")),
        parser_family_candidate=normalize_text(row.get("parser_family_candidate")),
        config_required=parse_bool(row.get("config_required")),
        config_path=normalize_text(row.get("config_path")),
        estimated_listing_count=parse_int(row.get("estimated_listing_count")),
        koop_signal=parse_bool(row.get("koop_signal")),
        huur_signal=parse_bool(row.get("huur_signal")),
        commercial_signal=parse_bool(row.get("commercial_signal")),
        project_signal=parse_bool(row.get("project_signal")),
        quality_score=parse_int(row.get("quality_score")),
        recommended_action=normalize_text(row.get("recommended_action")),
        priority_score=parse_int(row.get("priority_score")),
        evidence=evidence,
        last_reviewed_at=normalize_text(row.get("last_reviewed_at")),
        notes=notes,
    )

    if not record.source_id:
        record.source_id = make_source_id(
            record.source_domain,
            record.gemeente,
            record.source_name,
            record.homepage_url,
            record.aanbod_url,
        )

    apply_conservative_classification(record)
    if record.priority_score == 0:
        record.priority_score = compute_priority_score(record)
    if record.quality_score == 0:
        record.quality_score = compute_quality_score(record)
    return record


def normalize_aanbod_url_status(raw_status: object, aanbod_url: str) -> str:
    explicit = normalize_key(raw_status)
    if explicit in {"valid", "suspect", "missing"}:
        return explicit
    return "valid" if aanbod_url else "missing"


def apply_conservative_classification(record: SourceIntelligenceRecord) -> None:
    platform_text = " ".join(
        part for part in [normalize_key(record.detected_platform), normalize_key(record.technology_signals)] if part
    )

    if record.is_funda_dependent:
        record.delivery_mode = "funda_iframe_blocked"
        record.delivery_mode_confidence = 0.99
        record.parser_family_candidate = "iframe_blocked_handler"
        record.recommended_action = "blocked_no_bypass"
        record.access_status = "blocked"
        record.config_required = False
        return

    if record.is_pararius_dependent:
        record.delivery_mode = "pararius_external_blocked"
        record.delivery_mode_confidence = 0.99
        record.parser_family_candidate = "iframe_blocked_handler"
        record.recommended_action = "permission_required"
        record.access_status = "permission_required"
        record.config_required = False
        return

    if record.has_captcha:
        record.delivery_mode = "captcha_blocked"
        record.delivery_mode_confidence = 0.99
        record.parser_family_candidate = ""
        record.recommended_action = "blocked_no_bypass"
        record.access_status = "blocked"
        record.config_required = False
        return

    if record.has_login:
        record.delivery_mode = "login_required"
        record.delivery_mode_confidence = 0.98
        record.parser_family_candidate = ""
        record.recommended_action = "permission_required"
        record.access_status = "permission_required"
        record.config_required = False
        return

    if record.has_403:
        record.delivery_mode = "unknown_manual_review"
        record.delivery_mode_confidence = 0.90
        record.parser_family_candidate = ""
        record.recommended_action = "blocked_no_bypass"
        record.access_status = "blocked"
        record.config_required = False
        return

    if "realworks" in platform_text:
        record.delivery_mode = "realworks_public"
        record.delivery_mode_confidence = 0.98
        record.parser_family_candidate = "realworks_public"
        record.recommended_action = "build_source_config"
        record.access_status = record.access_status or "allowed"
        record.config_required = True
        return

    if "ogonline" in platform_text:
        record.delivery_mode = "ogonline_xhr"
        record.delivery_mode_confidence = 0.97
        record.parser_family_candidate = "ogonline_xhr"
        record.recommended_action = "build_source_config"
        record.access_status = record.access_status or "allowed"
        record.config_required = True
        return

    if "kolibri" in platform_text:
        record.delivery_mode = "kolibri_public"
        record.delivery_mode_confidence = 0.95
        record.parser_family_candidate = "kolibri_public"
        record.recommended_action = "research_before_parser"
        record.access_status = record.access_status or "allowed"
        record.config_required = True
        return

    if "wordpress" in platform_text and record.has_wp_json:
        record.delivery_mode = "wordpress_rest"
        record.delivery_mode_confidence = 0.92
        record.parser_family_candidate = "wordpress_rest"
        record.recommended_action = "build_source_config"
        record.access_status = record.access_status or "allowed"
        record.config_required = True
        return

    if "wordpress" in platform_text:
        record.delivery_mode = "wordpress_html_cards"
        record.delivery_mode_confidence = 0.82
        record.parser_family_candidate = "wordpress_html_cards"
        record.recommended_action = "build_source_config"
        record.access_status = record.access_status or "allowed"
        record.config_required = True
        return

    if record.has_iframe:
        record.delivery_mode = "iframe_external"
        record.delivery_mode_confidence = 0.85
        record.parser_family_candidate = "iframe_blocked_handler"
        record.recommended_action = "manual_review_needed"
        record.access_status = record.access_status or "researching"
        record.config_required = False
        return

    if record.has_json_ld:
        record.delivery_mode = "json_ld"
        record.delivery_mode_confidence = 0.76
        record.parser_family_candidate = "json_ld"
        record.recommended_action = "build_source_config"
        record.access_status = record.access_status or "allowed"
        record.config_required = True
        return

    if record.has_sitemap:
        record.delivery_mode = "sitemap_detail"
        record.delivery_mode_confidence = 0.72
        record.parser_family_candidate = "sitemap_detail"
        record.recommended_action = "research_before_parser"
        record.access_status = record.access_status or "allowed"
        record.config_required = True
        return

    if record.has_visible_cards:
        record.delivery_mode = "static_html_cards"
        record.delivery_mode_confidence = 0.68
        record.parser_family_candidate = "static_html_cards"
        record.recommended_action = "build_source_config"
        record.access_status = record.access_status or "allowed"
        record.config_required = True
        return

    record.delivery_mode = "unknown_manual_review"
    record.delivery_mode_confidence = 0.25
    record.parser_family_candidate = ""
    record.recommended_action = "manual_review_needed"
    record.access_status = record.access_status or "researching"
    record.config_required = False


def compute_priority_score(record: SourceIntelligenceRecord) -> int:
    score = 0

    if record.aanbod_url_status == "valid":
        score += 15
    elif record.aanbod_url_status == "suspect":
        score -= 8
    else:
        score -= 15

    if record.koop_signal:
        score += 12
    if record.estimated_listing_count >= 100:
        score += 12
    elif record.estimated_listing_count >= 40:
        score += 8
    elif record.estimated_listing_count > 0:
        score += 4

    delivery_bonus = {
        "realworks_public": 18,
        "ogonline_xhr": 16,
        "kolibri_public": 12,
        "wordpress_rest": 10,
        "wordpress_html_cards": 8,
        "static_html_cards": 7,
        "json_ld": 6,
        "sitemap_detail": 5,
    }
    score += delivery_bonus.get(record.delivery_mode, 0)

    if record.access_status == "legal_review":
        score -= 20
    elif record.access_status == "blocked":
        score -= 25
    elif record.access_status == "permission_required":
        score -= 10

    if record.has_captcha or record.has_login or record.has_403:
        score -= 20
    if record.is_funda_dependent:
        score -= 35
    if record.is_pararius_dependent:
        score -= 25
    if record.commercial_signal:
        score -= 12
    if record.huur_signal and not record.koop_signal:
        score -= 10
    if record.delivery_mode == "unknown_manual_review":
        score -= 6

    return score


def compute_quality_score(record: SourceIntelligenceRecord) -> int:
    score = 50
    if record.aanbod_url_status == "valid":
        score += 15
    elif record.aanbod_url_status == "suspect":
        score -= 10
    else:
        score -= 20

    if record.delivery_mode != "unknown_manual_review":
        score += 10
    if record.has_captcha or record.has_login or record.has_403:
        score -= 20
    if record.is_funda_dependent or record.is_pararius_dependent:
        score -= 15
    return max(0, min(100, score))
