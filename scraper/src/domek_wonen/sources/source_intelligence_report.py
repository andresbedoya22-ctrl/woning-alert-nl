from __future__ import annotations

from collections import Counter, defaultdict

from .source_intelligence_models import SourceIntelligenceRecord


def build_source_intelligence_report(records: list[SourceIntelligenceRecord]) -> dict[str, object]:
    manual_review_queue = sorted(
        [
            {
                "source_id": record.source_id,
                "source_domain": record.source_domain,
                "source_name": record.source_name,
                "aanbod_url": record.aanbod_url,
                "delivery_mode": record.delivery_mode,
                "parser_family_candidate": record.parser_family_candidate,
                "recommended_action": record.recommended_action,
                "priority_score": record.priority_score,
                "evidence": record.evidence,
            }
            for record in records
            if record.recommended_action in {"manual_review_needed", "blocked_no_bypass", "permission_required"}
        ],
        key=lambda item: (-int(item["priority_score"]), item["source_domain"], item["source_id"]),
    )

    grouped_priority: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "parser_family_candidate": "",
            "source_count": 0,
            "valid_aanbod_count": 0,
            "review_count": 0,
            "estimated_listing_count_total": 0,
            "priority_score_total": 0,
        }
    )
    for record in records:
        family = record.parser_family_candidate
        if not family:
            continue
        group = grouped_priority[family]
        group["parser_family_candidate"] = family
        group["source_count"] += 1
        group["valid_aanbod_count"] += 1 if record.aanbod_url_status == "valid" else 0
        group["review_count"] += 1 if record.recommended_action == "manual_review_needed" else 0
        group["estimated_listing_count_total"] += record.estimated_listing_count
        group["priority_score_total"] += record.priority_score

    parser_family_priority = sorted(
        grouped_priority.values(),
        key=lambda item: (
            -int(item["priority_score_total"]),
            -int(item["source_count"]),
            str(item["parser_family_candidate"]),
        ),
    )

    return {
        "total_sources": len(records),
        "unique_domains": len({record.source_domain for record in records if record.source_domain}),
        "counts_by_aanbod_url_status": _counts(records, lambda record: record.aanbod_url_status or "missing"),
        "counts_by_access_status": _counts(records, lambda record: record.access_status or "researching"),
        "counts_by_detected_platform": _counts(records, lambda record: record.detected_platform or "unknown"),
        "counts_by_delivery_mode": _counts(records, lambda record: record.delivery_mode or "unknown_manual_review"),
        "counts_by_parser_family_candidate": _counts(
            records, lambda record: record.parser_family_candidate or ""
        ),
        "counts_by_recommended_action": _counts(records, lambda record: record.recommended_action or ""),
        "manual_review_queue": manual_review_queue,
        "parser_family_priority": parser_family_priority,
    }


def _counts(records: list[SourceIntelligenceRecord], key_func) -> dict[str, int]:
    counter = Counter(key_func(record) for record in records)
    return dict(sorted(counter.items(), key=lambda item: item[0]))
