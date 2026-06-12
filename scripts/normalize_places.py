from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_CSV = BASE_DIR / "data" / "processed" / "sources_seed_noord_brabant.csv"
PLACE_MAP_CSV = BASE_DIR / "data" / "discovery" / "processed" / "noord_brabant_place_map.csv"
ENRICHED_CSV = BASE_DIR / "data" / "discovery" / "processed" / "sources_seed_with_gemeente.csv"
REPORT_MD = BASE_DIR / "data" / "discovery" / "reports" / "place_normalization_report.md"

PLACE_MAP_COLUMNS = [
    "raw_place",
    "normalized_place",
    "gemeente",
    "status",
    "notes",
]

ALLOWED_STATUS = {
    "current_gemeente",
    "alias",
    "former_gemeente",
    "needs_manual_review",
}

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
    "alphen chaam": {
        "normalized_place": "Alphen-Chaam",
        "gemeente": "Alphen-Chaam",
        "status": "alias",
        "notes": "Canonical municipality spelling uses a hyphen.",
    },
    "baarle nassau": {
        "normalized_place": "Baarle-Nassau",
        "gemeente": "Baarle-Nassau",
        "status": "alias",
        "notes": "Canonical municipality spelling uses a hyphen.",
    },
    "bergen op zoom": {
        "normalized_place": "Bergen op Zoom",
        "gemeente": "Bergen op Zoom",
        "status": "alias",
        "notes": "Normalize Dutch casing for op.",
    },
    "den bosch": {
        "normalized_place": "'s-Hertogenbosch",
        "gemeente": "'s-Hertogenbosch",
        "status": "alias",
        "notes": "Common alias for 's-Hertogenbosch.",
    },
    "etten leur": {
        "normalized_place": "Etten-Leur",
        "gemeente": "Etten-Leur",
        "status": "alias",
        "notes": "Canonical municipality spelling uses a hyphen.",
    },
    "geldrop mierlo": {
        "normalized_place": "Geldrop-Mierlo",
        "gemeente": "Geldrop-Mierlo",
        "status": "alias",
        "notes": "Canonical municipality spelling uses a hyphen.",
    },
    "gemert bakel": {
        "normalized_place": "Gemert-Bakel",
        "gemeente": "Gemert-Bakel",
        "status": "alias",
        "notes": "Canonical municipality spelling uses a hyphen.",
    },
    "gilze en rijen": {
        "normalized_place": "Gilze en Rijen",
        "gemeente": "Gilze en Rijen",
        "status": "alias",
        "notes": "Normalize Dutch casing for en.",
    },
    "heeze leende": {
        "normalized_place": "Heeze-Leende",
        "gemeente": "Heeze-Leende",
        "status": "alias",
        "notes": "Canonical municipality spelling uses a hyphen.",
    },
    "land van cuijk": {
        "normalized_place": "Land van Cuijk",
        "gemeente": "Land van Cuijk",
        "status": "alias",
        "notes": "Normalize Dutch casing for van.",
    },
    "landerd": {
        "normalized_place": "Maashorst",
        "gemeente": "Maashorst",
        "status": "former_gemeente",
        "notes": "Former municipality merged into Maashorst.",
    },
    "loon op zand": {
        "normalized_place": "Loon op Zand",
        "gemeente": "Loon op Zand",
        "status": "alias",
        "notes": "Normalize Dutch casing for op.",
    },
    "nuenen gerwen en nederwetten": {
        "normalized_place": "Nuenen, Gerwen en Nederwetten",
        "gemeente": "Nuenen, Gerwen en Nederwetten",
        "status": "alias",
        "notes": "Canonical municipality spelling includes a comma.",
    },
    "reusel de mierden": {
        "normalized_place": "Reusel-De Mierden",
        "gemeente": "Reusel-De Mierden",
        "status": "alias",
        "notes": "Canonical municipality spelling uses a hyphen.",
    },
    "s hertogenbosch": {
        "normalized_place": "'s-Hertogenbosch",
        "gemeente": "'s-Hertogenbosch",
        "status": "alias",
        "notes": "Normalize apostrophe and hyphen for the municipality name.",
    },
    "s-hertogenbosch": {
        "normalized_place": "'s-Hertogenbosch",
        "gemeente": "'s-Hertogenbosch",
        "status": "alias",
        "notes": "Normalize apostrophe for the municipality name.",
    },
    "sint michielsgestel": {
        "normalized_place": "Sint-Michielsgestel",
        "gemeente": "Sint-Michielsgestel",
        "status": "alias",
        "notes": "Canonical municipality spelling uses a hyphen.",
    },
    "son en breugel": {
        "normalized_place": "Son en Breugel",
        "gemeente": "Son en Breugel",
        "status": "alias",
        "notes": "Normalize Dutch casing for en.",
    },
}


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


def canonical_by_lookup() -> dict[str, str]:
    return {lookup_key(name): name for name in CURRENT_GEMEENTES}


CANONICAL_BY_LOOKUP = canonical_by_lookup()


def resolve_place(raw_place: str) -> dict[str, str]:
    raw_place = clean_spaces(raw_place)
    if not raw_place:
        return {
            "raw_place": "",
            "normalized_place": "Unknown",
            "gemeente": "Unknown",
            "status": "needs_manual_review",
            "notes": "Missing place value in seed.",
        }

    key = lookup_key(raw_place)
    explicit = EXPLICIT_MAPPINGS.get(key)
    if explicit:
        return {
            "raw_place": raw_place,
            "normalized_place": explicit["normalized_place"],
            "gemeente": explicit["gemeente"],
            "status": explicit["status"],
            "notes": explicit["notes"],
        }

    canonical = CANONICAL_BY_LOOKUP.get(key)
    if canonical:
        return {
            "raw_place": raw_place,
            "normalized_place": canonical,
            "gemeente": canonical,
            "status": "current_gemeente",
            "notes": "Matches a current municipality after whitespace cleanup.",
        }

    fallback = title_case_place(raw_place)
    return {
        "raw_place": raw_place,
        "normalized_place": fallback,
        "gemeente": fallback,
        "status": "needs_manual_review",
        "notes": "Fallback title-case normalization; municipality not recognized in current Noord-Brabant catalog.",
    }


def enrich_source_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    seen_places: dict[str, dict[str, str]] = {}
    enriched_rows: list[dict[str, str]] = []

    for row in rows:
        raw_place = clean_spaces(row.get("plaats", ""))
        resolved = resolve_place(raw_place)
        status = resolved["status"]
        if status not in ALLOWED_STATUS:
            raise ValueError(f"Invalid status generated for {raw_place!r}: {status}")

        seen_places.setdefault(raw_place, resolved)

        enriched_row = dict(row)
        enriched_row["raw_place"] = raw_place
        enriched_row["normalized_place"] = resolved["normalized_place"]
        enriched_row["gemeente"] = resolved["gemeente"]
        enriched_row["place_status"] = status
        enriched_row["place_review_reason"] = resolved["notes"] if status == "needs_manual_review" else ""
        enriched_rows.append(enriched_row)

    place_map_rows = sorted(seen_places.values(), key=lambda item: item["raw_place"].lower())
    return enriched_rows, place_map_rows


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


def write_report(source_rows: list[dict[str, str]], place_map_rows: list[dict[str, str]]) -> None:
    status_counts = Counter(row["status"] for row in place_map_rows)
    mappings_applied = [row for row in place_map_rows if row["status"] in {"alias", "former_gemeente"}]
    total_unique_gemeentes = len({row["gemeente"] for row in place_map_rows})

    report = "\n".join(
        [
            "# Place Normalization Report",
            "",
            "## Summary",
            f"- Total rows: {len(source_rows)}",
            f"- Total unique raw_place: {len(place_map_rows)}",
            f"- Total unique gemeente after normalization: {total_unique_gemeentes}",
            f"- Mappings applied: {len(mappings_applied)}",
            f"- former_gemeente count: {status_counts.get('former_gemeente', 0)}",
            f"- alias count: {status_counts.get('alias', 0)}",
            f"- needs_manual_review count: {status_counts.get('needs_manual_review', 0)}",
            "",
            "## Applied mappings",
            markdown_table(
                mappings_applied,
                ["raw_place", "normalized_place", "gemeente", "status", "notes"],
            ),
            "",
            "## Full raw_place to gemeente map",
            markdown_table(
                place_map_rows,
                ["raw_place", "normalized_place", "gemeente", "status", "notes"],
            ),
            "",
        ]
    )
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(report, encoding="utf-8")


def run() -> dict[str, int]:
    source_rows = read_csv_rows(INPUT_CSV)
    enriched_rows, place_map_rows = enrich_source_rows(source_rows)
    output_columns = list(source_rows[0].keys()) + [
        "raw_place",
        "normalized_place",
        "gemeente",
        "place_status",
        "place_review_reason",
    ]
    write_csv(PLACE_MAP_CSV, place_map_rows, PLACE_MAP_COLUMNS)
    write_csv(ENRICHED_CSV, enriched_rows, output_columns)
    write_report(source_rows, place_map_rows)
    return {
        "total_rows": len(source_rows),
        "unique_raw_places": len(place_map_rows),
        "unique_gemeentes": len({row["gemeente"] for row in place_map_rows}),
        "needs_manual_review": sum(1 for row in place_map_rows if row["status"] == "needs_manual_review"),
    }


if __name__ == "__main__":
    summary = run()
    print(
        "Place normalization complete: "
        f"rows={summary['total_rows']} "
        f"raw_places={summary['unique_raw_places']} "
        f"gemeentes={summary['unique_gemeentes']} "
        f"needs_manual_review={summary['needs_manual_review']}"
    )
