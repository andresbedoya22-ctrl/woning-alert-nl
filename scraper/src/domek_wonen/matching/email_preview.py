from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from .matching_v1 import DEFAULT_CLIENT_FIXTURE, ClientProfile, load_client_profile


DEFAULT_MATCHING_RUNS_DIR = Path("data/matching/runs")
DEFAULT_EMAIL_PREVIEW_RUNS_DIR = Path("data/email_previews/runs")
EMAIL_PREVIEW_HTML_FILENAME = "email_preview_es.html"
EMAIL_PREVIEW_REPORT_FILENAME = "email_preview_report.md"


@dataclass(frozen=True)
class EmailPreviewRunResult:
    run_id: str
    run_dir: Path
    results_csv_path: Path
    client_fixture_path: Path
    client_id: str
    html_path: Path
    report_path: Path
    total_rows: int
    total_passed: int
    excluded_missing_bedrooms: int
    excluded_outside_target_area: int
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
        rows = list(csv.DictReader(handle))

    passed_rows = [row for row in rows if row.get("hard_filter_passed", "").strip().casefold() == "true"]
    top_matches = passed_rows[:10]
    excluded_missing_bedrooms = sum(1 for row in rows if row.get("exclusion_reason", "") == "excluded_missing_bedrooms")
    excluded_outside_target_area = sum(1 for row in rows if row.get("exclusion_reason", "") == "excluded_outside_target_area")

    html_path = run_dir / EMAIL_PREVIEW_HTML_FILENAME
    html_path.write_text(
        _build_html(client, top_matches, excluded_missing_bedrooms, excluded_outside_target_area),
        encoding="utf-8",
    )

    report_path = run_dir / EMAIL_PREVIEW_REPORT_FILENAME
    report_path.write_text(
        _build_report(
            client=client,
            results_csv_path=results_csv_path,
            total_rows=len(rows),
            total_passed=len(passed_rows),
            excluded_missing_bedrooms=excluded_missing_bedrooms,
            excluded_outside_target_area=excluded_outside_target_area,
            top_matches=top_matches,
        ),
        encoding="utf-8",
    )

    return EmailPreviewRunResult(
        run_id=run_id,
        run_dir=run_dir,
        results_csv_path=results_csv_path,
        client_fixture_path=client_fixture_path,
        client_id=client.client_id,
        html_path=html_path,
        report_path=report_path,
        total_rows=len(rows),
        total_passed=len(passed_rows),
        excluded_missing_bedrooms=excluded_missing_bedrooms,
        excluded_outside_target_area=excluded_outside_target_area,
        top_matches=top_matches,
    )


def _build_html(
    client: ClientProfile,
    top_matches: list[dict[str, str]],
    excluded_missing_bedrooms: int,
    excluded_outside_target_area: int,
) -> str:
    cards = "\n".join(_render_match_card(index, row) for index, row in enumerate(top_matches, start=1))
    if not cards:
        cards = "<p class='empty'>No hay matches listos para mostrar.</p>"

    shortage_note = ""
    if len(top_matches) < 10:
        shortage_note = (
            "<p class='alert'>No hay suficientes matches con dormitorios confirmados. "
            f"Excluidas por missing bedrooms: {excluded_missing_bedrooms}. "
            f"Excluidas fuera de zona objetivo: {excluded_outside_target_area}.</p>"
        )

    return f"""<!DOCTYPE html>
<html lang="es">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Viviendas recomendadas para Cliente test Domek</title>
    <style>
      :root {{
        --bg: #f6f1e8;
        --panel: #fffaf2;
        --ink: #1f2a1f;
        --muted: #5c6758;
        --line: #d8cfbe;
        --accent: #1e6b52;
        --accent-soft: #dceee6;
        --warn: #8a5a00;
        --warn-soft: #f6e6c7;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: Georgia, "Times New Roman", serif;
        background: linear-gradient(180deg, #f4efe6 0%, #eae3d3 100%);
        color: var(--ink);
      }}
      main {{
        max-width: 960px;
        margin: 0 auto;
        padding: 32px 20px 48px;
      }}
      .hero, .card {{
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 18px;
        box-shadow: 0 14px 40px rgba(31, 42, 31, 0.08);
      }}
      .hero {{
        padding: 28px;
        margin-bottom: 20px;
      }}
      h1 {{
        margin: 0 0 12px;
        font-size: 2rem;
        line-height: 1.1;
      }}
      .summary, .meta, .warning-list {{
        color: var(--muted);
      }}
      .summary strong {{
        color: var(--ink);
      }}
      .alert {{
        margin: 0 0 20px;
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
        padding: 20px;
      }}
      .eyebrow {{
        color: var(--accent);
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }}
      h2 {{
        margin: 8px 0 6px;
        font-size: 1.3rem;
      }}
      .meta {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px 16px;
        margin: 12px 0;
      }}
      .pill {{
        display: inline-block;
        padding: 6px 10px;
        border-radius: 999px;
        background: var(--accent-soft);
        color: var(--accent);
        font-size: 0.9rem;
      }}
      .footer-note {{
        margin-top: 24px;
        color: var(--muted);
        font-size: 0.95rem;
      }}
      .empty {{
        padding: 20px;
        background: var(--panel);
        border-radius: 16px;
        border: 1px dashed var(--line);
      }}
      a {{ color: var(--accent); }}
    </style>
  </head>
  <body>
    <main>
      <section class="hero">
        <div class="eyebrow">Preview interno</div>
        <h1>Viviendas recomendadas para Cliente test Domek</h1>
        <p class="summary">
          <strong>Presupuesto:</strong> EUR {client.max_budget_eur:,}. 
          <strong>Zona objetivo:</strong> {escape(", ".join(client.target_cities))}. 
          <strong>Compatibles:</strong> {escape(", ".join(client.compatible_cities) or "-")}. 
          <strong>Dormitorios mínimos:</strong> {client.min_bedrooms}.
        </p>
        {shortage_note}
        <p class="footer-note">Vista previa interna. No enviada al cliente.</p>
      </section>
      <section class="grid">
        {cards}
      </section>
    </main>
  </body>
</html>
"""


def _render_match_card(index: int, row: dict[str, str]) -> str:
    warnings = [item.strip() for item in row.get("warnings", "").split(";") if item.strip()]
    warning_html = escape(", ".join(warnings)) if warnings else "Sin warnings principales"
    return f"""
<article class="card">
  <div class="eyebrow">Top {index}</div>
  <h2>{escape(row.get("address_raw", "") or "Dirección no disponible")}</h2>
  <div class="meta">
    <span class="pill">Ciudad: {escape(row.get("city_raw", "") or "-")}</span>
    <span class="pill">Precio: EUR {escape(row.get("price_eur", "") or "-")}</span>
    <span class="pill">Dormitorios: {escape(row.get("bedrooms_count", "") or "-")}</span>
    <span class="pill">m2: {escape(row.get("living_area_m2", "") or "-")}</span>
    <span class="pill">Energy label: {escape(row.get("energy_label", "") or "-")}</span>
    <span class="pill">Score: {escape(row.get("score", "") or "-")}</span>
  </div>
  <p class="warning-list">Warnings: {warning_html}</p>
  <p><a href="{escape(row.get("property_url", "") or "#")}">Ver anuncio</a></p>
</article>
""".strip()


def _build_report(
    *,
    client: ClientProfile,
    results_csv_path: Path,
    total_rows: int,
    total_passed: int,
    excluded_missing_bedrooms: int,
    excluded_outside_target_area: int,
    top_matches: list[dict[str, str]],
) -> str:
    top_lines = [
        "| # | property_id | city | bedrooms | m2 | score | warnings |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for index, row in enumerate(top_matches, start=1):
        top_lines.append(
            "| {index} | {property_id} | {city} | {bedrooms} | {m2} | {score} | {warnings} |".format(
                index=index,
                property_id=row.get("property_id", "") or "-",
                city=row.get("city_raw", "") or "-",
                bedrooms=row.get("bedrooms_count", "") or "-",
                m2=row.get("living_area_m2", "") or "-",
                score=row.get("score", "") or "-",
                warnings=row.get("warnings", "") or "-",
            )
        )
    if len(top_lines) == 2:
        top_lines.append("| - | - | - | - | - | - | No matches |")

    shortage_line = (
        f"- No hay suficientes matches con dormitorios confirmados. Excluidas por missing bedrooms: {excluded_missing_bedrooms}. Excluidas fuera de zona objetivo: {excluded_outside_target_area}"
        if len(top_matches) < 10
        else "- Top 10 completo con dormitorios confirmados."
    )

    return "\n".join(
        [
            "# Email Preview v1 Report",
            "",
            f"- Client fixture: {client.client_id}",
            f"- Matching results CSV: {results_csv_path}",
            f"- Total rows read: {total_rows}",
            f"- Total hard_filter_passed: {total_passed}",
            f"- Excluded outside target area: {excluded_outside_target_area}",
            f"- Excluded missing bedrooms: {excluded_missing_bedrooms}",
            shortage_line,
            "- Email sending: disabled",
            "",
            "## Top 10 renderizado",
            *top_lines,
            "",
        ]
    )


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
