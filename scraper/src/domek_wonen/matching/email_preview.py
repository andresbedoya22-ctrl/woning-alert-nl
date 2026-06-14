from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from .matching_v1 import (
    DEFAULT_CLIENT_FIXTURE,
    ClientProfile,
    _parse_bool,
    _parse_optional_int,
    _safe_int,
    load_client_profile,
)


DEFAULT_MATCHING_RUNS_DIR = Path("data/matching/runs")
DEFAULT_EMAIL_PREVIEW_RUNS_DIR = Path("data/email_previews/runs")
EMAIL_PREVIEW_ES_HTML_FILENAME = "email_preview_es.html"
EMAIL_PREVIEW_NL_HTML_FILENAME = "email_preview_nl.html"
ADVISOR_REVIEW_REPORT_FILENAME = "advisor_review_report.md"
EMAIL_PREVIEW_REPORT_FILENAME = ADVISOR_REVIEW_REPORT_FILENAME
DISPLAY_CLIENT_NAME = "Cliente test Domek"
MAX_RENDERED_MATCHES = 10
EXCLUSION_REASONS = (
    "excluded_outside_target_area",
    "excluded_missing_bedrooms",
    "excluded_over_budget",
    "excluded_bedrooms_below_min",
)
_REPORT_VALUE_RE = re.compile(r"^- ([^:]+): (.+)$", re.MULTILINE)


@dataclass(frozen=True)
class EmailPreviewRunResult:
    run_id: str
    run_dir: Path
    results_csv_path: Path
    matching_run_id: str
    inventory_run_id: str | None
    client_fixture_path: Path
    client_id: str
    html_path: Path
    html_es_path: Path
    html_nl_path: Path
    report_path: Path
    total_rows: int
    total_clean_available: int | None
    total_passed: int
    warning_counts: dict[str, int]
    exclusion_summary: dict[str, int | str]
    top_matches: list[dict[str, str]]


def find_latest_matching_results_csv(runs_base_dir: Path = DEFAULT_MATCHING_RUNS_DIR) -> Path:
    run_dirs = sorted(path for path in runs_base_dir.iterdir() if path.is_dir())
    if not run_dirs:
        raise FileNotFoundError(f"No Matching runs found in {runs_base_dir}")

    latest_run_dir = run_dirs[-1]
    results_csv_path = latest_run_dir / "matching_results.csv"
    if not results_csv_path.exists():
        raise FileNotFoundError(f"Missing matching_results.csv in {latest_run_dir}")
    return results_csv_path


def run_email_preview_v1(
    results_csv_path: Path,
    client_fixture_path: Path = DEFAULT_CLIENT_FIXTURE,
    email_preview_runs_dir: Path = DEFAULT_EMAIL_PREVIEW_RUNS_DIR,
) -> EmailPreviewRunResult:
    client = load_client_profile(client_fixture_path)
    run_id = _utc_run_id()
    run_dir = email_preview_runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    with results_csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = tuple(reader.fieldnames or ())

    passed_rows = [row for row in rows if row.get("hard_filter_passed", "").strip().casefold() == "true"]
    top_matches = passed_rows[:MAX_RENDERED_MATCHES]
    warning_counts = _summarize_warnings(passed_rows)
    exclusion_summary = _summarize_exclusions(rows, fieldnames)
    matching_metadata = _read_matching_run_metadata(results_csv_path)

    html_es_path = run_dir / EMAIL_PREVIEW_ES_HTML_FILENAME
    html_es_path.write_text(
        _build_html(
            language="es",
            client=client,
            top_matches=top_matches,
            total_passed=len(passed_rows),
            exclusion_summary=exclusion_summary,
        ),
        encoding="utf-8",
    )

    html_nl_path = run_dir / EMAIL_PREVIEW_NL_HTML_FILENAME
    html_nl_path.write_text(
        _build_html(
            language="nl",
            client=client,
            top_matches=top_matches,
            total_passed=len(passed_rows),
            exclusion_summary=exclusion_summary,
        ),
        encoding="utf-8",
    )

    report_path = run_dir / ADVISOR_REVIEW_REPORT_FILENAME
    report_path.write_text(
        _build_advisor_review_report(
            client=client,
            client_fixture_path=client_fixture_path,
            results_csv_path=results_csv_path,
            total_rows=len(rows),
            total_passed=len(passed_rows),
            total_clean_available=matching_metadata.get("total_clean_available"),
            inventory_run_id=matching_metadata.get("inventory_run_id"),
            matching_run_id=results_csv_path.parent.name,
            exclusion_summary=exclusion_summary,
            warning_counts=warning_counts,
            top_matches=top_matches,
        ),
        encoding="utf-8",
    )

    return EmailPreviewRunResult(
        run_id=run_id,
        run_dir=run_dir,
        results_csv_path=results_csv_path,
        matching_run_id=results_csv_path.parent.name,
        inventory_run_id=_normalize_nullable_value(matching_metadata.get("inventory_run_id")),
        client_fixture_path=client_fixture_path,
        client_id=client.client_id,
        html_path=html_es_path,
        html_es_path=html_es_path,
        html_nl_path=html_nl_path,
        report_path=report_path,
        total_rows=len(rows),
        total_clean_available=_parse_optional_int(matching_metadata.get("total_clean_available")),
        total_passed=len(passed_rows),
        warning_counts=warning_counts,
        exclusion_summary=exclusion_summary,
        top_matches=top_matches,
    )


def _build_html(
    *,
    language: str,
    client: ClientProfile,
    top_matches: list[dict[str, str]],
    total_passed: int,
    exclusion_summary: dict[str, int | str],
) -> str:
    if language == "nl":
        copy = {
            "lang": "nl",
            "title": f"Interne review voor {DISPLAY_CLIENT_NAME}",
            "eyebrow": "Interne preview",
            "headline": f"Woningselectie voor {DISPLAY_CLIENT_NAME}",
            "summary": (
                f"Budget: EUR {_format_number(client.max_budget_eur)} · "
                f"Doelgebied: {escape(', '.join(client.target_cities))} · "
                f"Compatibel: {escape(', '.join(client.compatible_cities) or '-')} · "
                f"Min. slaapkamers: {client.min_bedrooms}"
            ),
            "body_note": "Lokale review-output. Er worden geen e-mails verzonden.",
            "count_note": f"{len(top_matches)} van maximaal {MAX_RENDERED_MATCHES} aanbevelingen weergegeven uit {total_passed} matches die door de harde filters kwamen.",
            "empty": "Er zijn momenteel geen aanbevolen woningen om te tonen.",
            "address_fallback": "Adres niet beschikbaar",
            "why_title": "Waarom verschijnt deze woning",
            "warnings_label": "Warnings",
            "link_label": "Bekijk advertentie",
            "shortage": _build_shortage_message(language, exclusion_summary),
        }
    else:
        copy = {
            "lang": "es",
            "title": f"Revisión interna para {DISPLAY_CLIENT_NAME}",
            "eyebrow": "Preview interno",
            "headline": f"Viviendas recomendadas para {DISPLAY_CLIENT_NAME}",
            "summary": (
                f"Presupuesto: EUR {_format_number(client.max_budget_eur)} · "
                f"Zona objetivo: {escape(', '.join(client.target_cities))} · "
                f"Compatibles: {escape(', '.join(client.compatible_cities) or '-')} · "
                f"Dormitorios mínimos: {client.min_bedrooms}"
            ),
            "body_note": "Vista previa interna. No enviada al cliente.",
            "count_note": f"Se muestran {len(top_matches)} de un máximo de {MAX_RENDERED_MATCHES} recomendaciones sobre {total_passed} matches que pasaron filtros duros.",
            "empty": "No hay viviendas recomendadas para mostrar ahora mismo.",
            "address_fallback": "Dirección no disponible",
            "why_title": "Por qué aparece esta vivienda",
            "warnings_label": "Warnings",
            "link_label": "Ver anuncio",
            "shortage": _build_shortage_message(language, exclusion_summary),
        }

    cards = "\n".join(
        _render_match_card(language=language, client=client, index=index, row=row, address_fallback=copy["address_fallback"], why_title=copy["why_title"], warnings_label=copy["warnings_label"], link_label=copy["link_label"])
        for index, row in enumerate(top_matches, start=1)
    )
    if not cards:
        cards = f"<p class='empty'>{copy['empty']}</p>"

    shortage_html = f"<p class='alert'>{copy['shortage']}</p>" if copy["shortage"] else ""

    return f"""<!DOCTYPE html>
<html lang="{copy['lang']}">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{copy['title']}</title>
    <style>
      :root {{
        --bg-top: #efe8da;
        --bg-bottom: #f8f5ef;
        --panel: #fffdf8;
        --ink: #1f2933;
        --muted: #5b6873;
        --line: #d7decb;
        --accent: #1f5f4a;
        --accent-soft: #e6f1eb;
        --warn: #7a4f01;
        --warn-soft: #f9ebc9;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
        color: var(--ink);
        background:
          radial-gradient(circle at top left, rgba(31, 95, 74, 0.08), transparent 30%),
          linear-gradient(180deg, var(--bg-top) 0%, var(--bg-bottom) 100%);
      }}
      main {{
        max-width: 1120px;
        margin: 0 auto;
        padding: 32px 20px 56px;
      }}
      .hero, .card {{
        background: var(--panel);
        border: 1px solid rgba(31, 95, 74, 0.12);
        border-radius: 18px;
        box-shadow: 0 14px 32px rgba(31, 41, 51, 0.08);
      }}
      .hero {{
        padding: 28px;
        margin-bottom: 18px;
      }}
      .eyebrow {{
        color: var(--accent);
        font-size: 0.8rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }}
      h1 {{
        margin: 10px 0 12px;
        font-size: 2rem;
        line-height: 1.15;
      }}
      .summary, .count-note, .footer-note, .why {{
        color: var(--muted);
      }}
      .summary strong {{
        color: var(--ink);
      }}
      .alert {{
        margin: 16px 0 0;
        padding: 14px 16px;
        background: var(--warn-soft);
        color: var(--warn);
        border-radius: 14px;
      }}
      .grid {{
        display: grid;
        gap: 16px;
      }}
      .card {{
        padding: 22px;
      }}
      .card-top {{
        display: flex;
        justify-content: space-between;
        gap: 12px;
        align-items: flex-start;
      }}
      h2 {{
        margin: 8px 0 6px;
        font-size: 1.25rem;
      }}
      .score {{
        min-width: 96px;
        text-align: center;
        padding: 10px 12px;
        border-radius: 14px;
        background: var(--accent-soft);
        color: var(--accent);
        font-weight: 700;
      }}
      .meta {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
        gap: 10px;
        margin: 16px 0;
      }}
      .meta-item {{
        padding: 12px 14px;
        border-radius: 14px;
        background: #f5f8f2;
        border: 1px solid rgba(31, 95, 74, 0.09);
      }}
      .meta-label {{
        display: block;
        font-size: 0.78rem;
        font-weight: 700;
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
      }}
      .why-box {{
        margin-top: 14px;
        padding: 14px 16px;
        border-radius: 14px;
        background: #f7f3ea;
        border: 1px solid rgba(31, 41, 51, 0.08);
      }}
      .why-box h3 {{
        margin: 0 0 8px;
        font-size: 1rem;
      }}
      .warnings {{
        margin: 14px 0 0;
        color: var(--muted);
      }}
      .footer-note {{
        margin-top: 18px;
      }}
      .empty {{
        padding: 20px;
        background: var(--panel);
        border-radius: 16px;
        border: 1px dashed var(--line);
      }}
      a {{
        color: var(--accent);
        text-decoration-thickness: 1px;
      }}
      @media (max-width: 720px) {{
        .card-top {{
          flex-direction: column;
        }}
        .score {{
          min-width: 0;
        }}
      }}
    </style>
  </head>
  <body>
    <main>
      <section class="hero">
        <div class="eyebrow">{copy['eyebrow']}</div>
        <h1>{copy['headline']}</h1>
        <p class="summary">{copy['summary']}</p>
        <p class="count-note">{copy['count_note']}</p>
        {shortage_html}
        <p class="footer-note">{copy['body_note']}</p>
      </section>
      <section class="grid">
        {cards}
      </section>
    </main>
  </body>
</html>
"""


def _render_match_card(
    *,
    language: str,
    client: ClientProfile,
    index: int,
    row: dict[str, str],
    address_fallback: str,
    why_title: str,
    warnings_label: str,
    link_label: str,
) -> str:
    warnings = [item.strip() for item in row.get("warnings", "").split(";") if item.strip()]
    warnings_text = ", ".join(warnings) if warnings else _translate(language, "none")
    why_text = _explain_match(language=language, client=client, row=row)
    return f"""
<article class="card">
  <div class="card-top">
    <div>
      <div class="eyebrow">Top {index}</div>
      <h2>{escape(row.get("address_raw", "") or address_fallback)}</h2>
    </div>
    <div class="score">Score<br />{escape(row.get("score", "") or "-")}</div>
  </div>
  <div class="meta">
    {_render_meta_item(language, "address", row.get("address_raw", "") or address_fallback)}
    {_render_meta_item(language, "city", row.get("city_raw", "") or "-")}
    {_render_meta_item(language, "price", _format_currency(row.get("price_eur", "")))}
    {_render_meta_item(language, "bedrooms", row.get("bedrooms_count", "") or "-")}
    {_render_meta_item(language, "m2", _format_m2(row.get("living_area_m2", "")))}
    {_render_meta_item(language, "energy_label", row.get("energy_label", "") or "-")}
  </div>
  <p><a href="{escape(row.get("property_url", "") or "#")}">{link_label}</a></p>
  <div class="why-box">
    <h3>{why_title}</h3>
    <p class="why">{escape(why_text)}</p>
  </div>
  <p class="warnings">{warnings_label}: {escape(warnings_text)}</p>
</article>
""".strip()


def _build_advisor_review_report(
    *,
    client: ClientProfile,
    client_fixture_path: Path,
    results_csv_path: Path,
    total_rows: int,
    total_passed: int,
    total_clean_available: str | None,
    inventory_run_id: str | None,
    matching_run_id: str,
    exclusion_summary: dict[str, int | str],
    warning_counts: dict[str, int],
    top_matches: list[dict[str, str]],
) -> str:
    top_lines = [
        "| # | property_id | address | city | price_eur | bedrooms | m2 | energy | score | warnings |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for index, row in enumerate(top_matches, start=1):
        top_lines.append(
            "| {index} | {property_id} | {address} | {city} | {price} | {bedrooms} | {m2} | {energy} | {score} | {warnings} |".format(
                index=index,
                property_id=row.get("property_id", "") or "-",
                address=row.get("address_raw", "") or "-",
                city=row.get("city_raw", "") or "-",
                price=row.get("price_eur", "") or "-",
                bedrooms=row.get("bedrooms_count", "") or "-",
                m2=row.get("living_area_m2", "") or "-",
                energy=row.get("energy_label", "") or "-",
                score=row.get("score", "") or "-",
                warnings=row.get("warnings", "") or "-",
            )
        )
    if len(top_lines) == 2:
        top_lines.append("| - | - | - | - | - | - | - | - | - | No matches |")

    warning_lines = ["- None"] if not warning_counts else [
        f"- {warning}: {count}" for warning, count in sorted(warning_counts.items(), key=lambda item: (-item[1], item[0]))
    ]

    recommendation_lines = _manual_review_recommendations(top_matches=top_matches, warning_counts=warning_counts)
    exclusion_lines = [
        f"- {reason}: {value}" for reason, value in exclusion_summary.items()
    ]

    return "\n".join(
        [
            "# Advisor Review Report v1",
            "",
            f"- Client used: {DISPLAY_CLIENT_NAME} ({client.client_id})",
            f"- Client fixture path: {client_fixture_path}",
            f"- Matching results CSV: {results_csv_path}",
            f"- Inventory run used: {inventory_run_id or 'not available in current output'}",
            f"- Matching run used: {matching_run_id}",
            f"- Total rows read: {total_rows}",
            f"- Total clean_available: {total_clean_available or 'not available in current output'}",
            f"- Total hard_filter_passed: {total_passed}",
            "",
            "## Excluded summary",
            *exclusion_lines,
            "",
            "## Top matches",
            *top_lines,
            "",
            "## Principales warnings",
            *warning_lines,
            "",
            "## Recomendaciones para revisión manual",
            *recommendation_lines,
            "",
        ]
    )


def _read_matching_run_metadata(results_csv_path: Path) -> dict[str, str]:
    report_path = results_csv_path.parent / "matching_report.md"
    if not report_path.exists():
        return {}

    text = report_path.read_text(encoding="utf-8")
    metadata: dict[str, str] = {}
    for key, value in _REPORT_VALUE_RE.findall(text):
        normalized_key = key.strip().casefold()
        if normalized_key == "inventory run used":
            metadata["inventory_run_id"] = value.strip()
        elif normalized_key == "total clean_available read":
            metadata["total_clean_available"] = value.strip()
    return metadata


def _summarize_warnings(rows: list[dict[str, str]]) -> dict[str, int]:
    warning_counts: dict[str, int] = {}
    for row in rows:
        for warning in (item.strip() for item in row.get("warnings", "").split(";")):
            if warning:
                warning_counts[warning] = warning_counts.get(warning, 0) + 1
    return warning_counts


def _summarize_exclusions(rows: list[dict[str, str]], fieldnames: tuple[str, ...]) -> dict[str, int | str]:
    if "exclusion_reason" not in fieldnames:
        return {reason: "not available in current output" for reason in EXCLUSION_REASONS}

    summary = {reason: 0 for reason in EXCLUSION_REASONS}
    for row in rows:
        reason = row.get("exclusion_reason", "").strip()
        if reason in summary:
            summary[reason] += 1
    return summary


def _build_shortage_message(language: str, exclusion_summary: dict[str, int | str]) -> str:
    outside_area = exclusion_summary.get("excluded_outside_target_area", "not available in current output")
    missing_bedrooms = exclusion_summary.get("excluded_missing_bedrooms", "not available in current output")
    if language == "nl":
        return (
            "Niet alle tien plekken zijn altijd gevuld. "
            f"Buiten doelgebied: {outside_area}. "
            f"Ontbrekende slaapkamers: {missing_bedrooms}."
        )
    return (
        "No siempre se llenan las diez posiciones. "
        f"Excluidas por outside_target_area: {outside_area}. "
        f"Excluidas por missing_bedrooms: {missing_bedrooms}."
    )


def _explain_match(*, language: str, client: ClientProfile, row: dict[str, str]) -> str:
    reasons: list[str] = []

    price_eur = _safe_int(row.get("price_eur", ""))
    if price_eur is not None and price_eur <= client.max_budget_eur:
        gap = client.max_budget_eur - price_eur
        if language == "nl":
            reasons.append(f"valt binnen budget en blijft EUR {_format_number(gap)} onder het maximum")
        else:
            reasons.append(f"queda dentro del presupuesto y se mantiene EUR {_format_number(gap)} por debajo del máximo")

    city = row.get("city_raw", "").strip()
    if city:
        if city in client.preferred_cities:
            reasons.append(_translate(language, "preferred_city", city))
        elif city in client.target_cities or city in client.compatible_cities:
            reasons.append(_translate(language, "target_area", city))

    bedrooms = _parse_optional_int(row.get("bedrooms_count"))
    if bedrooms is not None and bedrooms >= client.min_bedrooms:
        reasons.append(_translate(language, "bedrooms_ok", str(bedrooms)))

    m2 = _parse_optional_int(row.get("living_area_m2"))
    if m2 is not None and m2 >= client.min_m2:
        reasons.append(_translate(language, "m2_ok", str(m2)))

    energy_label = (row.get("energy_label", "") or "").strip().upper()
    if energy_label and energy_label in client.preferred_energy_labels:
        reasons.append(_translate(language, "energy_ok", energy_label))

    if _row_has_outdoor_space(row):
        reasons.append(_translate(language, "outdoor_ok"))

    score = row.get("score", "") or "-"
    if reasons:
        joined = "; ".join(reasons[:4])
        return _translate(language, "explanation", score, joined)
    return _translate(language, "fallback_explanation", score)


def _manual_review_recommendations(
    *,
    top_matches: list[dict[str, str]],
    warning_counts: dict[str, int],
) -> list[str]:
    recommendations = [
        "- Verificar manualmente que los warnings más repetidos no oculten datos clave en el anuncio original.",
        "- Confirmar disponibilidad y vigencia del precio en los top matches antes de compartirlos por otro canal.",
    ]
    if warning_counts.get("missing_energy_label"):
        recommendations.append("- Revisar manualmente el energy label en los anuncios con `missing_energy_label`.")
    if warning_counts.get("missing_m2"):
        recommendations.append("- Completar m2 manualmente donde falte para afinar el orden final de recomendación.")
    if warning_counts.get("missing_rooms"):
        recommendations.append("- Validar número de rooms cuando falte, aunque no afecte el hard filter actual.")
    if any(not row.get("property_url", "").strip() for row in top_matches):
        recommendations.append("- Corregir links vacíos antes de usar esta revisión como base comercial.")
    return recommendations


def _render_meta_item(language: str, key: str, value: str) -> str:
    labels = {
        "es": {
            "address": "Dirección",
            "city": "Ciudad",
            "price": "Precio",
            "bedrooms": "Dormitorios",
            "m2": "m2",
            "energy_label": "Energy label",
        },
        "nl": {
            "address": "Adres",
            "city": "Plaats",
            "price": "Prijs",
            "bedrooms": "Slaapkamers",
            "m2": "m2",
            "energy_label": "Energielabel",
        },
    }
    label = labels[language][key]
    return (
        f"<div class='meta-item'><span class='meta-label'>{escape(label)}</span>"
        f"{escape(value)}</div>"
    )


def _format_currency(value: str) -> str:
    amount = _safe_int(value)
    if amount is None:
        return "-"
    return f"EUR {_format_number(amount)}"


def _format_m2(value: str) -> str:
    amount = _safe_int(value)
    if amount is None:
        return "-"
    return f"{amount} m2"


def _format_number(value: int) -> str:
    return f"{value:,}"


def _row_has_outdoor_space(row: dict[str, str]) -> bool:
    return _parse_bool(row.get("has_garden", "")) or _parse_bool(row.get("has_balcony", ""))


def _normalize_nullable_value(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _translate(language: str, key: str, *args: str) -> str:
    translations = {
        "es": {
            "none": "Sin warnings principales",
            "preferred_city": "está en ciudad preferida ({0})",
            "target_area": "cumple la zona objetivo ({0})",
            "bedrooms_ok": "cumple con {0} dormitorios",
            "m2_ok": "ofrece {0} m2 útiles",
            "energy_ok": "tiene energy label preferido ({0})",
            "outdoor_ok": "incluye señal de jardín o balcón",
            "explanation": "Score {0}. Aparece porque {1}.",
            "fallback_explanation": "Score {0}. Aparece por pasar filtros duros y mantener señales suficientes para revisión.",
        },
        "nl": {
            "none": "Geen hoofdwarnings",
            "preferred_city": "ligt in een voorkeursplaats ({0})",
            "target_area": "valt binnen het doelgebied ({0})",
            "bedrooms_ok": "heeft {0} slaapkamers",
            "m2_ok": "biedt {0} m2 woonoppervlak",
            "energy_ok": "heeft een voorkeurslabel ({0})",
            "outdoor_ok": "heeft een tuin- of balkon-signaal",
            "explanation": "Score {0}. Deze woning verschijnt omdat hij {1}.",
            "fallback_explanation": "Score {0}. Deze woning verschijnt omdat hij de harde filters haalt en genoeg signalen heeft voor review.",
        },
    }
    return translations[language][key].format(*args)


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
