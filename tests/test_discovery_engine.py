from pathlib import Path
import shutil
import sys
import csv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.discovery.engine import LATEST_DIR, RUNS_DIR, run_discovery


def test_run_discovery_creates_expected_outputs() -> None:
    before = {path.name for path in RUNS_DIR.iterdir()} if RUNS_DIR.exists() else set()

    output = run_discovery(
        province="noord-brabant",
        mode="full",
        max_queries=500,
        max_sites=20,
    )

    try:
        assert output.report_path.exists()
        assert (output.run_dir / "candidate_domains.csv").exists()
        assert (output.run_dir / "discovered_sources.csv").exists()
        assert (output.run_dir / "rejected_candidates.csv").exists()
        assert (output.run_dir / "generated_queries.csv").exists()
        assert (LATEST_DIR / "candidate_domains.csv").exists()
        report_text = output.report_path.read_text(encoding="utf-8")
        assert "Search API status: disabled_missing_credentials" in report_text
        assert "External discovery enabled: false" in report_text
        assert "Coverage By Gemeente" in report_text
        assert "Missing Expected Gemeenten" in report_text
        assert "- Veldhoven" in report_text
        assert "- Valkenswaard" in report_text
        assert (
            output.analyzed_candidates_count
            == output.discovered_sources_count
            + output.rejected_candidates_count
            + output.deduped_candidates_count
            + output.skipped_candidates_count
        )
        with (output.run_dir / "generated_queries.csv").open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        assert any(row["gemeente"] == "Veldhoven" for row in rows)
    finally:
        if output.run_dir.exists():
            shutil.rmtree(output.run_dir)
        for filename in (
            "candidate_domains.csv",
            "discovered_sources.csv",
            "rejected_candidates.csv",
            "generated_queries.csv",
            "discovery_run_report.md",
        ):
            latest_file = LATEST_DIR / filename
            if latest_file.exists():
                latest_file.unlink()
        remaining = {path.name for path in RUNS_DIR.iterdir()} if RUNS_DIR.exists() else set()
        assert remaining == before
