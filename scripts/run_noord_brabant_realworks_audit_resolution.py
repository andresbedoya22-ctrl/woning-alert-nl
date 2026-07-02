from __future__ import annotations

import argparse
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.pilots.noord_brabant_realworks_audit import resolve_noord_brabant_realworks_audit


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve Noord-Brabant Realworks Audit v1.")
    parser.add_argument("--audit-summary", required=True)
    parser.add_argument("--audit-workbook", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-workbook", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = resolve_noord_brabant_realworks_audit(
        audit_summary_csv=Path(args.audit_summary),
        audit_workbook=Path(args.audit_workbook),
        output_csv=Path(args.output_csv),
        output_workbook=Path(args.output_workbook),
    )
    print(result.output_csv_path, flush=True)
    print(result.output_workbook_path, flush=True)
    for key in sorted(result.metrics):
        print(f"{key}={result.metrics[key]}", flush=True)
    print(f"final_decision={result.decision.final_decision}", flush=True)
    print(f"merge_recommended={result.decision.merge_recommended}", flush=True)
    print(f"recommended_next_action={result.decision.recommended_next_action}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
