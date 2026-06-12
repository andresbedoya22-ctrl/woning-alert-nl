from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from unicodedata import normalize as unicode_normalize
from urllib.parse import urlsplit, urlunsplit


BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_CSV = BASE_DIR / "data" / "raw" / "makelaars_noord_brabant_raw.csv"
OUTPUT_CSV = BASE_DIR / "data" / "processed" / "sources_seed_noord_brabant.csv"
OUTPUT_REPORT = BASE_DIR / "data" / "processed" / "sources_seed_report.md"

OUTPUT_COLUMNS = [
    "office_name",
    "website",
    "domain",
    "root_domain",
    "koopaanbod_url",
    "koopaanbod_url_quality",
    "plaats",
    "provincie",
    "source_type",
    "discovery_source",
    "confidence",
    "needs_review",
    "review_reason",
    "notes",
]

DISCOVERY_SOURCE = "nvm_harvester_2026_06_12"
PROVINCIE = "Noord-Brabant"
SOURCE_TYPE = "makelaar_site"

MULTI_PART_SUFFIXES = {
    "co.uk",
    "org.uk",
    "gov.uk",
    "ac.uk",
    "co.jp",
    "com.au",
    "net.au",
    "org.au",
    "co.nz",
}

VALID_KOOPAANBOD_SIGNALS = (
    "aanbod",
    "koop",
    "koopwoningen",
    "woningaanbod",
    "wonen",
    "huizen",
    "woningen",
    "objecten",
)

INVALID_KOOPAANBOD_SIGNALS = (
    "gratis-verkoopadvies",
    "verkoopadvies",
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
    "algemene-voorwaarden",
    "reviews",
    "aankoopmakelaar",
    "verkoopmakelaar",
)


@dataclass
class ImportStats:
    input_records: int
    output_records: int
    duplicates_removed: int
    with_website: int
    with_koopaanbod_url: int
    koopaanbod_url_valid_count: int
    koopaanbod_url_suspect_count: int
    koopaanbod_url_missing_count: int
    needs_review_count: int
    duplicate_root_domains: list[tuple[str, int]]
    suspect_koopaanbod_urls: list[tuple[str, str, str]]
    unmapped_columns: list[str]


def canonicalize_column_name(value: str) -> str:
    value = (value or "").strip().lower()
    replacements = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ü": "u",
        "ñ": "n",
    }
    for src, target in replacements.items():
        value = value.replace(src, target)
    return "".join(ch for ch in value if ch.isalnum())


def normalize_url(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    parts = urlsplit(raw)
    scheme = parts.scheme.lower() or "https"
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/")
    normalized = urlunsplit((scheme, netloc, path, parts.query, ""))
    return normalized.rstrip("/") if path == "" and not parts.query else normalized


def sanitize_note_text(value: str) -> str:
    sanitized = (value or "").strip()
    if not sanitized:
        return ""
    replacements = {
        "home no cargó": "home did not load",
        "home no cargÃ³": "home did not load",
        "revisión manual": "manual review",
        "revision manual": "manual review",
    }
    lowered = sanitized.lower()
    for source, target in replacements.items():
        if source in lowered:
            sanitized = target
            lowered = sanitized.lower()
    ascii_text = (
        unicode_normalize("NFKD", sanitized).encode("ascii", "ignore").decode("ascii")
    )
    return " ".join(ascii_text.split())


def extract_domain(url: str) -> str:
    if not url:
        return ""
    parts = urlsplit(url)
    host = parts.netloc.lower().strip()
    if host.startswith("www."):
        host = host[4:]
    if ":" in host:
        host = host.split(":", 1)[0]
    return host


def extract_root_domain(domain: str) -> str:
    domain = (domain or "").strip().lower()
    if not domain:
        return ""
    parts = [part for part in domain.split(".") if part]
    if len(parts) < 2:
        return ""
    suffix = ".".join(parts[-2:])
    if len(parts) >= 3 and suffix in MULTI_PART_SUFFIXES:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def compute_confidence(website: str, koopaanbod_url: str) -> float:
    if website and koopaanbod_url:
        return 0.85
    if website:
        return 0.65
    return 0.40


def is_valid_koopaanbod_url(url: str) -> tuple[bool, str]:
    normalized_url = normalize_url(url)
    if not normalized_url:
        return False, "missing url"

    parsed = urlsplit(normalized_url)
    haystack = f"{parsed.netloc}{parsed.path}".lower()

    if "bedrijfshuisvesting" in haystack and not any(
        token in haystack for token in ("koop", "woning", "wonen")
    ):
        return False, "contains bedrijfshuisvesting without residential listing signal"

    for signal in INVALID_KOOPAANBOD_SIGNALS:
        if signal in haystack:
            return False, f"contains excluded token '{signal}'"

    if any(signal in haystack for signal in VALID_KOOPAANBOD_SIGNALS):
        return True, "valid"

    return False, "missing listing signal"


def compute_needs_review(
    website: str,
    root_domain: str,
    koopaanbod_url: str,
    koopaanbod_url_quality: str = "valid",
) -> bool:
    return not (website and root_domain and koopaanbod_url) or koopaanbod_url_quality == "suspect"


def append_unique(target: list[str], value: str) -> None:
    cleaned = sanitize_note_text(value)
    if cleaned and cleaned not in target:
        target.append(cleaned)


def join_unique(values: list[str]) -> str:
    return "; ".join(dict.fromkeys(values))


def detect_column_mapping(fieldnames: Iterable[str]) -> tuple[dict[str, str], list[str]]:
    aliases = {
        "office_name": {"office_name", "naam", "name", "officename", "makelaar"},
        "website": {"website", "site", "url", "web", "homepage"},
        "koopaanbod_url": {
            "koopaanbodurl",
            "koopurl",
            "aanbodurl",
            "woningaanbodurl",
            "listingurl",
        },
        "plaats": {"plaats", "city", "town", "municipality", "gemeente", "localidad"},
        "notes": {"notes", "notas", "remark", "remarks", "opmerking", "opmerkingen"},
    }
    normalized_fields = {canonicalize_column_name(name): name for name in fieldnames}
    mapping: dict[str, str] = {}
    for target, names in aliases.items():
        for candidate in names:
            actual = normalized_fields.get(canonicalize_column_name(candidate))
            if actual:
                mapping[target] = actual
                break
    used = set(mapping.values())
    unmapped = [name for name in fieldnames if name not in used]
    return mapping, unmapped


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


def build_notes_and_review_reason(
    row: dict[str, str],
    mapping: dict[str, str],
    domain: str,
    root_domain: str,
    koopaanbod_url: str,
    koopaanbod_url_quality: str,
    koopaanbod_reason: str,
) -> tuple[str, str]:
    notes: list[str] = []
    review_reasons: list[str] = []
    raw_notes = row.get(mapping.get("notes", ""), "").strip() if mapping.get("notes") else ""
    if raw_notes:
        append_unique(notes, raw_notes)
    if not row.get(mapping.get("website", ""), "").strip():
        append_unique(notes, "missing website")
        review_reasons.append("missing website")
    if not row.get(mapping.get("koopaanbod_url", ""), "").strip():
        append_unique(notes, "missing koopaanbod_url")
        review_reasons.append("missing koopaanbod_url")
    if not domain:
        append_unique(notes, "missing domain")
        review_reasons.append("missing domain")
    if not root_domain:
        append_unique(notes, "missing root_domain")
        review_reasons.append("missing root_domain")
    if koopaanbod_url_quality == "suspect":
        append_unique(notes, f"suspect koopaanbod_url: {koopaanbod_reason}")
        review_reasons.append(f"suspect koopaanbod_url: {koopaanbod_reason}")
    return join_unique(notes), join_unique(review_reasons)


def score_row(row: dict[str, str]) -> tuple[float, int, int, int]:
    return (
        float(row["confidence"]),
        1 if row["koopaanbod_url"] else 0,
        1 if row["website"] else 0,
        len(row["notes"]),
    )


def normalize_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], ImportStats]:
    if not rows:
        stats = ImportStats(0, 0, 0, 0, 0, 0, 0, 0, [], [], [])
        return [], stats

    fieldnames = list(rows[0].keys())
    mapping, unmapped_columns = detect_column_mapping(fieldnames)

    normalized_rows: list[dict[str, str]] = []
    root_domains_seen: list[str] = []
    for row in rows:
        office_name = row.get(mapping.get("office_name", ""), "").strip()
        plaats = row.get(mapping.get("plaats", ""), "").strip()
        website = normalize_url(row.get(mapping.get("website", ""), ""))
        koopaanbod_url = normalize_url(row.get(mapping.get("koopaanbod_url", ""), ""))
        domain = extract_domain(website or koopaanbod_url)
        root_domain = extract_root_domain(domain)
        confidence = compute_confidence(website, koopaanbod_url)
        if not koopaanbod_url:
            koopaanbod_url_quality = "missing"
            koopaanbod_reason = "missing koopaanbod_url"
        else:
            is_valid, koopaanbod_reason = is_valid_koopaanbod_url(koopaanbod_url)
            koopaanbod_url_quality = "valid" if is_valid else "suspect"
            if koopaanbod_url_quality == "suspect":
                confidence = min(confidence, 0.65)
        needs_review = compute_needs_review(website, root_domain, koopaanbod_url, koopaanbod_url_quality)
        notes, review_reason = build_notes_and_review_reason(
            row,
            mapping,
            domain,
            root_domain,
            koopaanbod_url,
            koopaanbod_url_quality,
            koopaanbod_reason,
        )

        normalized = {
            "office_name": office_name,
            "website": website,
            "domain": domain,
            "root_domain": root_domain,
            "koopaanbod_url": koopaanbod_url,
            "koopaanbod_url_quality": koopaanbod_url_quality,
            "plaats": plaats,
            "provincie": PROVINCIE,
            "source_type": SOURCE_TYPE,
            "discovery_source": DISCOVERY_SOURCE,
            "confidence": f"{confidence:.2f}",
            "needs_review": "true" if needs_review else "false",
            "review_reason": review_reason,
            "notes": notes,
        }
        normalized_rows.append(normalized)
        if root_domain:
            root_domains_seen.append(root_domain)

    deduped: dict[tuple[str, str], dict[str, str]] = {}
    for row in normalized_rows:
        key = (
            row["root_domain"].lower() if row["root_domain"] else f"missing::{row['office_name'].lower()}",
            row["plaats"].lower(),
        )
        current = deduped.get(key)
        if current is None or score_row(row) > score_row(current):
            deduped[key] = row

    duplicate_root_domains = [
        (root_domain, count)
        for root_domain, count in Counter(root_domains_seen).most_common(20)
        if count > 1
    ]
    output_rows = sorted(
        deduped.values(),
        key=lambda item: (item["plaats"].lower(), item["office_name"].lower(), item["root_domain"].lower()),
    )
    stats = ImportStats(
        input_records=len(rows),
        output_records=len(output_rows),
        duplicates_removed=len(normalized_rows) - len(output_rows),
        with_website=sum(1 for row in output_rows if row["website"]),
        with_koopaanbod_url=sum(1 for row in output_rows if row["koopaanbod_url"]),
        koopaanbod_url_valid_count=sum(1 for row in output_rows if row["koopaanbod_url_quality"] == "valid"),
        koopaanbod_url_suspect_count=sum(1 for row in output_rows if row["koopaanbod_url_quality"] == "suspect"),
        koopaanbod_url_missing_count=sum(1 for row in output_rows if row["koopaanbod_url_quality"] == "missing"),
        needs_review_count=sum(1 for row in output_rows if row["needs_review"] == "true"),
        duplicate_root_domains=duplicate_root_domains,
        suspect_koopaanbod_urls=[
            (row["office_name"], row["koopaanbod_url"], row["review_reason"])
            for row in output_rows
            if row["koopaanbod_url_quality"] == "suspect"
        ][:20],
        unmapped_columns=unmapped_columns,
    )
    return output_rows, stats


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "_Sin filas_"
    header = "| " + " | ".join(OUTPUT_COLUMNS) + " |"
    separator = "| " + " | ".join("---" for _ in OUTPUT_COLUMNS) + " |"
    body = []
    for row in rows:
        values = [row[column].replace("\n", " ").replace("|", "\\|") for column in OUTPUT_COLUMNS]
        body.append("| " + " | ".join(values) + " |")
    return "\n".join([header, separator, *body])


def write_report(path: Path, rows: list[dict[str, str]], stats: ImportStats) -> None:
    top_duplicates = (
        "\n".join(f"- `{root_domain}`: {count}" for root_domain, count in stats.duplicate_root_domains)
        if stats.duplicate_root_domains
        else "- Ninguno"
    )
    warnings = []
    if stats.unmapped_columns:
        warnings.append("Columnas no mapeadas: " + ", ".join(f"`{name}`" for name in stats.unmapped_columns))
    if any(row["needs_review"] == "true" for row in rows):
        warnings.append("Hay registros marcados para manual review.")
    warnings_block = "\n".join(f"- {warning}" for warning in warnings) if warnings else "- Ninguna"
    suspect_rows_table = (
        "\n".join(
            [
                "| office_name | koopaanbod_url | reason |",
                "| --- | --- | --- |",
                *[
                    f"| {office_name.replace('|', '\\|')} | {url.replace('|', '\\|')} | {reason.replace('|', '\\|')} |"
                    for office_name, url, reason in stats.suspect_koopaanbod_urls
                ],
            ]
        )
        if stats.suspect_koopaanbod_urls
        else "_Sin URLs sospechosas_"
    )

    report = "\n".join(
        [
            "# Sources Seed Report",
            "",
            "## Resumen",
            f"- Registros de entrada: {stats.input_records}",
            f"- Registros de salida: {stats.output_records}",
            f"- Duplicados eliminados: {stats.duplicates_removed}",
            f"- Cantidad con website: {stats.with_website}",
            f"- Cantidad con koopaanbod_url: {stats.with_koopaanbod_url}",
            f"- koopaanbod_url valid: {stats.koopaanbod_url_valid_count}",
            f"- koopaanbod_url suspect: {stats.koopaanbod_url_suspect_count}",
            f"- koopaanbod_url missing: {stats.koopaanbod_url_missing_count}",
            f"- Cantidad needs_review: {stats.needs_review_count}",
            "",
            "## Top 20 root_domain repetidos",
            top_duplicates,
            "",
            "## Top 20 suspect koopaanbod_url",
            suspect_rows_table,
            "",
            "## Primeras 20 filas limpias",
            markdown_table(rows[:20]),
            "",
            "## Advertencias",
            warnings_block,
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")


def run_import() -> ImportStats:
    rows = read_csv_rows(INPUT_CSV)
    normalized_rows, stats = normalize_rows(rows)
    write_csv(OUTPUT_CSV, normalized_rows)
    write_report(OUTPUT_REPORT, normalized_rows, stats)
    return stats


if __name__ == "__main__":
    stats = run_import()
    print(
        f"Import complete: input={stats.input_records} output={stats.output_records} "
        f"duplicates_removed={stats.duplicates_removed}"
    )
