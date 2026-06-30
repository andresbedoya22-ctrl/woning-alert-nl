from __future__ import annotations

import argparse
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.sources.coverage_census import run_noord_brabant_coverage_source_census


DEFAULT_OUTPUT_DIR = BASE_DIR / "tmp" / "generated"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Noord-Brabant Coverage Source Census v1.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Local generated output directory.")
    parser.add_argument("--max-sources", type=int, default=None, help="Optional source cap for diagnostics.")
    parser.add_argument(
        "--allow-live-http",
        action="store_true",
        help="Enable bounded standard-library HTTP. Default uses local evidence only.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=10.0, help="Per-request timeout when live HTTP is enabled.")
    parser.add_argument(
        "--max-requests-per-domain",
        type=int,
        default=3,
        help="Conservative per-domain request cap when live HTTP is enabled.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_noord_brabant_coverage_source_census(
        repo_root=BASE_DIR,
        output_dir=Path(args.output_dir),
        allow_live_http=args.allow_live_http,
        max_sources=args.max_sources,
        max_requests_per_domain=args.max_requests_per_domain,
        timeout_seconds=args.timeout_seconds,
    )
    metrics = result.quality_metrics
    print(result.workbook_path, flush=True)
    print(result.master_csv_path, flush=True)
    print(result.review_queue_csv_path, flush=True)
    print(f"total_sources={metrics['total_sources']}", flush=True)
    print(f"deduped_sources={metrics['deduped_sources']}", flush=True)
    print(f"in_scope_noord_brabant_coverage_sources={metrics['in_scope_noord_brabant_coverage_sources']}", flush=True)
    print(f"operational_unknown_family_count={metrics['operational_unknown_family_count']}", flush=True)
    print(
        "missing_aanbod_url_without_terminal_reason_count="
        f"{metrics['missing_aanbod_url_without_terminal_reason_count']}",
        flush=True,
    )
    print(f"quality_gate_passed={metrics['quality_gate_passed']}", flush=True)
    return 0 if metrics["quality_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
