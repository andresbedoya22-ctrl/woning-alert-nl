from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_CSV = BASE_DIR / "data" / "processed" / "sources_seed_noord_brabant.csv"
ENRICHED_INPUT_CSV = BASE_DIR / "data" / "discovery" / "processed" / "sources_seed_with_gemeente.csv"
OUTPUT_CSV = BASE_DIR / "data" / "discovery" / "processed" / "gemeente_coverage.csv"
OUTPUT_REPORT = BASE_DIR / "data" / "discovery" / "reports" / "gemeente_coverage_report.md"

OUTPUT_COLUMNS = [
    "gemeente",
    "total_sources",
    "with_website",
    "with_valid_koopaanbod_url",
    "with_suspect_koopaanbod_url",
    "missing_koopaanbod_url",
    "needs_review_count",
    "needs_review_rate",
    "valid_aanbod_rate",
    "zero_valid_aanbod",
    "high_review_rate",
    "low_count",
    "important_city",
    "priority_score",
    "recommendation",
]

IMPORTANT_CITIES = {
    "eindhoven",
    "tilburg",
    "breda",
    "den bosch",
    "'s-hertogenbosch",
    "helmond",
    "oss",
    "roosendaal",
    "bergen op zoom",
    "waalwijk",
    "veldhoven",
    "oosterhout",
    "etten-leur",
    "uden",
    "veghel",
    "boxtel",
    "best",
}


@dataclass(frozen=True)
class CoverageSummary:
    total_rows: int
    total_places: int
    total_valid: int
    total_suspect: int
    total_missing: int
    total_needs_review: int
    places_with_zero_valid: int
    important_places_in_seed: int


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    encodings = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
    last_error: UnicodeDecodeError | None = None
    for encoding in encodings:
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle))
        except UnicodeDecodeError as exc:
            last_error = exc
    raise RuntimeError(f"No se pudo leer el CSV con encodings soportados: {last_error}")


def resolve_input_csv() -> Path:
    if ENRICHED_INPUT_CSV.exists():
        return ENRICHED_INPUT_CSV
    return DEFAULT_INPUT_CSV


def normalize_place(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def is_truthy(value: str) -> bool:
    return normalize_place(value) in {"true", "1", "yes"}


def rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def bool_str(value: bool) -> str:
    return "true" if value else "false"


def format_rate(value: float) -> str:
    return f"{value:.4f}"


def compute_priority_score(
    total_sources: int,
    with_valid_koopaanbod_url: int,
    needs_review_rate: float,
    valid_aanbod_rate: float,
    important_city: bool,
) -> int:
    score = 0
    if with_valid_koopaanbod_url == 0:
        score += 40
    if total_sources <= 2:
        score += 25
    if needs_review_rate >= 0.50:
        score += 20
    if important_city:
        score += 20
    if valid_aanbod_rate < 0.50:
        score += 10
    return score


def build_recommendation(row: dict[str, str]) -> str:
    if row["zero_valid_aanbod"] == "true":
        return "No valid koopaanbod URLs; source discovery gap."
    if row["high_review_rate"] == "true":
        return "High review rate; verify websites and aanbod links."
    if row["low_count"] == "true":
        return "Low source count; expand local makelaar coverage."
    if row["important_city"] == "true":
        return "Important city with room to improve aanbod coverage."
    return "Improve valid aanbod coverage and reduce manual review."


def get_group_name(row: dict[str, str]) -> str:
    gemeente = (row.get("gemeente") or "").strip()
    if gemeente:
        return gemeente
    plaats = (row.get("plaats") or "").strip()
    if plaats:
        return plaats
    return "Unknown"


def aggregate_by_gemeente(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, dict[str, int | str]] = {}
    for row in rows:
        gemeente = get_group_name(row)
        bucket = grouped.setdefault(
            gemeente,
            {
                "gemeente": gemeente,
                "total_sources": 0,
                "with_website": 0,
                "with_valid_koopaanbod_url": 0,
                "with_suspect_koopaanbod_url": 0,
                "missing_koopaanbod_url": 0,
                "needs_review_count": 0,
            },
        )
        bucket["total_sources"] += 1
        if (row.get("website") or "").strip():
            bucket["with_website"] += 1
        quality = normalize_place(row.get("koopaanbod_url_quality", ""))
        if quality == "valid":
            bucket["with_valid_koopaanbod_url"] += 1
        elif quality == "suspect":
            bucket["with_suspect_koopaanbod_url"] += 1
        else:
            bucket["missing_koopaanbod_url"] += 1
        if is_truthy(row.get("needs_review", "")):
            bucket["needs_review_count"] += 1

    output_rows: list[dict[str, str]] = []
    for gemeente, bucket in grouped.items():
        total_sources = int(bucket["total_sources"])
        with_valid = int(bucket["with_valid_koopaanbod_url"])
        needs_review_count = int(bucket["needs_review_count"])
        needs_review_rate = rate(needs_review_count, total_sources)
        valid_aanbod_rate = rate(with_valid, total_sources)
        important_city = normalize_place(gemeente) in IMPORTANT_CITIES
        priority_score = compute_priority_score(
            total_sources=total_sources,
            with_valid_koopaanbod_url=with_valid,
            needs_review_rate=needs_review_rate,
            valid_aanbod_rate=valid_aanbod_rate,
            important_city=important_city,
        )
        output_row = {
            "gemeente": gemeente,
            "total_sources": str(total_sources),
            "with_website": str(int(bucket["with_website"])),
            "with_valid_koopaanbod_url": str(with_valid),
            "with_suspect_koopaanbod_url": str(int(bucket["with_suspect_koopaanbod_url"])),
            "missing_koopaanbod_url": str(int(bucket["missing_koopaanbod_url"])),
            "needs_review_count": str(needs_review_count),
            "needs_review_rate": format_rate(needs_review_rate),
            "valid_aanbod_rate": format_rate(valid_aanbod_rate),
            "zero_valid_aanbod": bool_str(with_valid == 0),
            "high_review_rate": bool_str(needs_review_rate >= 0.50),
            "low_count": bool_str(total_sources <= 2),
            "important_city": bool_str(important_city),
            "priority_score": str(priority_score),
        }
        output_row["recommendation"] = build_recommendation(output_row)
        output_rows.append(output_row)

    return sorted(
        output_rows,
        key=lambda row: (
            -int(row["priority_score"]),
            -float(row["needs_review_rate"]),
            float(row["valid_aanbod_rate"]),
            int(row["total_sources"]),
            row["gemeente"].lower(),
        ),
    )


def aggregate_by_place(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return aggregate_by_gemeente(rows)


def compute_summary(rows: list[dict[str, str]]) -> CoverageSummary:
    return CoverageSummary(
        total_rows=sum(int(row["total_sources"]) for row in rows),
        total_places=len(rows),
        total_valid=sum(int(row["with_valid_koopaanbod_url"]) for row in rows),
        total_suspect=sum(int(row["with_suspect_koopaanbod_url"]) for row in rows),
        total_missing=sum(int(row["missing_koopaanbod_url"]) for row in rows),
        total_needs_review=sum(int(row["needs_review_count"]) for row in rows),
        places_with_zero_valid=sum(1 for row in rows if row["zero_valid_aanbod"] == "true"),
        important_places_in_seed=sum(1 for row in rows if row["important_city"] == "true"),
    )


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(rows: list[dict[str, str]], columns: list[str]) -> str:
    if not rows:
        return "_Sin filas_"
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body = []
    for row in rows:
        values = [str(row[column]).replace("|", "\\|") for column in columns]
        body.append("| " + " | ".join(values) + " |")
    return "\n".join([header, separator, *body])


def top_best_coverage(rows: list[dict[str, str]], limit: int = 20) -> list[dict[str, str]]:
    return sorted(
        rows,
        key=lambda row: (
            -float(row["valid_aanbod_rate"]),
            float(row["needs_review_rate"]),
            -int(row["with_valid_koopaanbod_url"]),
            -int(row["total_sources"]),
            row["gemeente"].lower(),
        ),
    )[:limit]


def top_worst_coverage(rows: list[dict[str, str]], limit: int = 20) -> list[dict[str, str]]:
    return sorted(
        rows,
        key=lambda row: (
            float(row["valid_aanbod_rate"]),
            -float(row["needs_review_rate"]),
            int(row["with_valid_koopaanbod_url"]),
            int(row["total_sources"]),
            -int(row["priority_score"]),
            row["gemeente"].lower(),
        ),
    )[:limit]


def important_city_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        row
        for row in sorted(rows, key=lambda item: (-int(item["priority_score"]), item["gemeente"].lower()))
        if row["important_city"] == "true"
    ]


def top_recommendations(rows: list[dict[str, str]], limit: int = 10) -> list[dict[str, str]]:
    return sorted(
        rows,
        key=lambda row: (
            -int(row["priority_score"]),
            -float(row["needs_review_rate"]),
            float(row["valid_aanbod_rate"]),
            int(row["total_sources"]),
            row["gemeente"].lower(),
        ),
    )[:limit]


def recommendation_reason(row: dict[str, str]) -> str:
    if row["zero_valid_aanbod"] == "true":
        return "zero_valid_aanbod"
    if row["high_review_rate"] == "true":
        return "high_review_rate"
    if row["low_count"] == "true":
        return "low_count"
    if row["important_city"] == "true":
        return "important_city"
    if float(row["valid_aanbod_rate"]) < 0.50:
        return "valid_aanbod_rate_below_0_50"
    return "general_improvement"


def write_report(path: Path, rows: list[dict[str, str]]) -> None:
    summary = compute_summary(rows)
    seed_valid_rate = rate(summary.total_valid, summary.total_rows)
    seed_review_rate = rate(summary.total_needs_review, summary.total_rows)
    best_rows = top_best_coverage(rows)
    worst_rows = top_worst_coverage(rows)
    important_rows = important_city_rows(rows)
    recommendation_rows = top_recommendations(rows)

    overview_table_columns = [
        "gemeente",
        "total_sources",
        "with_valid_koopaanbod_url",
        "needs_review_rate",
        "valid_aanbod_rate",
        "priority_score",
    ]
    important_table_columns = [
        "gemeente",
        "total_sources",
        "with_valid_koopaanbod_url",
        "needs_review_count",
        "needs_review_rate",
        "valid_aanbod_rate",
        "priority_score",
        "recommendation",
    ]

    recommendation_lines = [
        f"- `{row['gemeente']}`: {recommendation_reason(row)}."
        for row in recommendation_rows
    ]

    report = "\n".join(
        [
            "# Gemeente Coverage Report",
            "",
            "## Resumen total del seed",
            f"- Total sources: {summary.total_rows}",
            f"- Total gemeenten: {summary.total_places}",
            f"- With valid koopaanbod_url: {summary.total_valid} ({seed_valid_rate:.2%})",
            f"- With suspect koopaanbod_url: {summary.total_suspect}",
            f"- Missing koopaanbod_url: {summary.total_missing}",
            f"- Needs review: {summary.total_needs_review} ({seed_review_rate:.2%})",
            f"- Gemeenten with zero valid aanbod: {summary.places_with_zero_valid}",
            f"- Important gemeenten present in seed: {summary.important_places_in_seed}",
            "",
            "## Top 20 gemeenten con mejor cobertura",
            markdown_table(best_rows, overview_table_columns),
            "",
            "## Top 20 gemeenten con peor cobertura",
            markdown_table(worst_rows, overview_table_columns),
            "",
            "## Important gemeenten",
            markdown_table(important_rows, important_table_columns),
            "",
            "## Recomendaciones concretas",
            "### Top 10 gemeenten a atacar primero",
            *recommendation_lines,
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")


def run_analysis() -> CoverageSummary:
    source_rows = read_csv_rows(resolve_input_csv())
    coverage_rows = aggregate_by_gemeente(source_rows)
    write_csv(OUTPUT_CSV, coverage_rows)
    write_report(OUTPUT_REPORT, coverage_rows)
    return compute_summary(coverage_rows)


if __name__ == "__main__":
    summary = run_analysis()
    print(
        f"Coverage analysis complete: gemeenten={summary.total_places} "
        f"sources={summary.total_rows} zero_valid_gemeenten={summary.places_with_zero_valid}"
    )
