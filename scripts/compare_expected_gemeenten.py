from __future__ import annotations

import csv
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
COVERAGE_CSV = BASE_DIR / "data" / "discovery" / "processed" / "gemeente_coverage.csv"
EXPECTED_CSV = BASE_DIR / "data" / "discovery" / "reference" / "noord_brabant_gemeenten_expected.csv"
OUTPUT_CSV = BASE_DIR / "data" / "discovery" / "processed" / "gemeente_coverage_with_expected.csv"
OUTPUT_REPORT = BASE_DIR / "data" / "discovery" / "reports" / "missing_gemeenten_report.md"
EXISTING_REPORT = BASE_DIR / "data" / "discovery" / "reports" / "gemeente_coverage_report.md"

OUTPUT_COLUMNS = [
    "gemeente",
    "region_group",
    "is_important",
    "notes",
    "present_in_seed",
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
    "missing_completely",
    "low_coverage",
    "priority_score_adjusted",
]


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


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def bool_str(value: bool) -> str:
    return "true" if value else "false"


def int_str(value: int) -> str:
    return str(value)


def parse_int(value: str, default: int = 0) -> int:
    try:
        return int((value or "").strip())
    except ValueError:
        return default


def markdown_table(rows: list[dict[str, str]], columns: list[str]) -> str:
    if not rows:
        return "_Sin filas_"
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body = []
    for row in rows:
        values = [str(row.get(column, "")).replace("|", "\\|") for column in columns]
        body.append("| " + " | ".join(values) + " |")
    return "\n".join([header, separator, *body])


def build_joined_rows(
    expected_rows: list[dict[str, str]], coverage_rows: list[dict[str, str]]
) -> list[dict[str, str]]:
    coverage_by_gemeente = {row["gemeente"]: row for row in coverage_rows}
    joined_rows: list[dict[str, str]] = []

    for expected in expected_rows:
        gemeente = expected["gemeente"]
        coverage = coverage_by_gemeente.get(gemeente)
        present_in_seed = coverage is not None
        total_sources = parse_int(coverage["total_sources"]) if coverage else 0
        with_valid = parse_int(coverage["with_valid_koopaanbod_url"]) if coverage else 0
        missing_completely = not present_in_seed
        low_coverage = total_sources <= 2 or with_valid <= 1
        is_important = (expected.get("is_important") or "").strip().lower() == "true"
        base_priority = parse_int(coverage["priority_score"], default=100) if coverage else 100
        priority_score_adjusted = base_priority
        if missing_completely:
            priority_score_adjusted += 40
        if low_coverage:
            priority_score_adjusted += 25
        if is_important:
            priority_score_adjusted += 20

        output_row = {column: "" for column in OUTPUT_COLUMNS}
        output_row["gemeente"] = gemeente
        output_row["region_group"] = expected.get("region_group", "")
        output_row["is_important"] = expected.get("is_important", "")
        output_row["notes"] = expected.get("notes", "")
        output_row["present_in_seed"] = bool_str(present_in_seed)
        output_row["missing_completely"] = bool_str(missing_completely)
        output_row["low_coverage"] = bool_str(low_coverage)
        output_row["priority_score_adjusted"] = int_str(priority_score_adjusted)

        if coverage:
            for column in OUTPUT_COLUMNS:
                if column in coverage:
                    output_row[column] = coverage[column]
            output_row["region_group"] = expected.get("region_group", "")
            output_row["is_important"] = expected.get("is_important", "")
            output_row["notes"] = expected.get("notes", "")
            output_row["present_in_seed"] = "true"
            output_row["missing_completely"] = bool_str(missing_completely)
            output_row["low_coverage"] = bool_str(low_coverage)
            output_row["priority_score_adjusted"] = int_str(priority_score_adjusted)
        else:
            output_row["total_sources"] = "0"
            output_row["with_website"] = "0"
            output_row["with_valid_koopaanbod_url"] = "0"
            output_row["with_suspect_koopaanbod_url"] = "0"
            output_row["missing_koopaanbod_url"] = "0"
            output_row["needs_review_count"] = "0"
            output_row["needs_review_rate"] = "0.0000"
            output_row["valid_aanbod_rate"] = "0.0000"
            output_row["zero_valid_aanbod"] = "true"
            output_row["high_review_rate"] = "false"
            output_row["low_count"] = "true"
            output_row["important_city"] = bool_str(is_important)
            output_row["priority_score"] = "100"
            output_row["recommendation"] = "Missing completely from current seed coverage."

        joined_rows.append(output_row)

    return sorted(
        joined_rows,
        key=lambda row: (
            -parse_int(row["priority_score_adjusted"]),
            row["missing_completely"] != "true",
            row["low_coverage"] != "true",
            row["gemeente"].lower(),
        ),
    )


def build_report(rows: list[dict[str, str]]) -> str:
    total_expected = len(rows)
    present_count = sum(1 for row in rows if row["present_in_seed"] == "true")
    missing_count = sum(1 for row in rows if row["missing_completely"] == "true")
    low_coverage_count = sum(1 for row in rows if row["low_coverage"] == "true")

    missing_rows = [row for row in rows if row["missing_completely"] == "true"]
    low_coverage_rows = [
        row for row in rows if row["low_coverage"] == "true" and row["missing_completely"] != "true"
    ]
    top_priority_rows = sorted(
        rows,
        key=lambda row: (
            -parse_int(row["priority_score_adjusted"]),
            row["missing_completely"] != "true",
            row["low_coverage"] != "true",
            -parse_int(row["total_sources"]),
            row["gemeente"].lower(),
        ),
    )[:15]

    missing_columns = [
        "gemeente",
        "region_group",
        "is_important",
        "present_in_seed",
        "priority_score_adjusted",
        "notes",
    ]
    low_coverage_columns = [
        "gemeente",
        "region_group",
        "is_important",
        "total_sources",
        "with_valid_koopaanbod_url",
        "low_coverage",
        "priority_score_adjusted",
    ]
    top_priority_columns = [
        "gemeente",
        "region_group",
        "is_important",
        "present_in_seed",
        "missing_completely",
        "total_sources",
        "with_valid_koopaanbod_url",
        "low_coverage",
        "priority_score_adjusted",
    ]

    return "\n".join(
        [
            "# Missing Gemeenten Report",
            "",
            "## Summary",
            f"- Total expected gemeenten: {total_expected}",
            f"- Present in seed: {present_count}",
            f"- Missing completely: {missing_count}",
            f"- Low coverage: {low_coverage_count}",
            "",
            "## Missing completely",
            markdown_table(missing_rows, missing_columns),
            "",
            "## Low coverage",
            markdown_table(low_coverage_rows, low_coverage_columns),
            "",
            "## Top 15 priority gemeenten for discovery",
            markdown_table(top_priority_rows, top_priority_columns),
            "",
        ]
    )


def update_existing_report(rows: list[dict[str, str]]) -> None:
    if not EXISTING_REPORT.exists():
        return

    content = EXISTING_REPORT.read_text(encoding="utf-8")
    marker = "## Expected reference cross-check"
    if marker in content:
        return

    total_expected = len(rows)
    present_count = sum(1 for row in rows if row["present_in_seed"] == "true")
    missing_count = sum(1 for row in rows if row["missing_completely"] == "true")
    low_coverage_count = sum(1 for row in rows if row["low_coverage"] == "true")

    appendix = "\n".join(
        [
            "",
            marker,
            f"- Expected gemeenten reference: {total_expected}",
            f"- Present in seed: {present_count}",
            f"- Missing completely: {missing_count}",
            f"- Low coverage against expected reference: {low_coverage_count}",
            "- Detailed report: `data/discovery/reports/missing_gemeenten_report.md`",
            "",
        ]
    )
    EXISTING_REPORT.write_text(content.rstrip() + "\n" + appendix, encoding="utf-8")


def main() -> None:
    coverage_rows = read_csv_rows(COVERAGE_CSV)
    expected_rows = read_csv_rows(EXPECTED_CSV)
    joined_rows = build_joined_rows(expected_rows, coverage_rows)
    write_csv(OUTPUT_CSV, joined_rows, OUTPUT_COLUMNS)
    OUTPUT_REPORT.write_text(build_report(joined_rows), encoding="utf-8")
    update_existing_report(joined_rows)

    missing_count = sum(1 for row in joined_rows if row["missing_completely"] == "true")
    low_coverage_count = sum(1 for row in joined_rows if row["low_coverage"] == "true")
    print(
        "Expected gemeenten comparison complete: "
        f"expected={len(joined_rows)} missing={missing_count} low_coverage={low_coverage_count}"
    )


if __name__ == "__main__":
    main()
