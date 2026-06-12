from __future__ import annotations

import csv
from pathlib import Path

from .config import DEFAULT_GEMEENTEN_REFERENCE_PATH, QUERY_TEMPLATES
from .models import GeneratedQuery


def load_reference_gemeenten(path: Path = DEFAULT_GEMEENTEN_REFERENCE_PATH) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(handle)
        return [row["gemeente"].strip() for row in rows if (row.get("gemeente") or "").strip()]


def generate_queries_for_gemeente(
    gemeente: str,
    provincie: str = "",
    max_queries: int | None = None,
) -> list[GeneratedQuery]:
    limit = len(QUERY_TEMPLATES) if max_queries is None else max(0, min(max_queries, len(QUERY_TEMPLATES)))
    return [
        GeneratedQuery(
            gemeente=gemeente,
            provincie=provincie,
            template=template,
            query=template.format(gemeente=gemeente),
        )
        for template in QUERY_TEMPLATES[:limit]
    ]


def generate_queries_from_reference(
    path: Path = DEFAULT_GEMEENTEN_REFERENCE_PATH,
    provincie: str = "",
    max_queries: int | None = None,
) -> list[GeneratedQuery]:
    queries: list[GeneratedQuery] = []
    for gemeente in load_reference_gemeenten(path):
        queries.extend(generate_queries_for_gemeente(gemeente=gemeente, provincie=provincie, max_queries=max_queries))
    return queries
