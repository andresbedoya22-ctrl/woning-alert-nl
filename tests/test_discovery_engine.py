from pathlib import Path
import csv
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.discovery.engine import LATEST_DIR, RUNS_DIR, run_discovery
from domek_wonen.discovery.models import SourceCandidate
from domek_wonen.discovery.overpass_adapter import OverpassDiscoveryResponse


class StubOverpassAdapter:
    def __init__(self, candidates: list[SourceCandidate], status: str = "ok") -> None:
        self._response = OverpassDiscoveryResponse(
            status=status,
            candidates=candidates,
            raw_candidates=len(candidates),
            candidates_with_website=sum(1 for candidate in candidates if candidate.website),
            candidates_without_website=sum(1 for candidate in candidates if not candidate.website),
            endpoint_used="stub://overpass",
        )

    def discover(self, province: str) -> OverpassDiscoveryResponse:
        assert province == "Noord-Brabant"
        return self._response


def _cleanup_output(output) -> None:
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


def test_run_discovery_creates_expected_outputs() -> None:
    before = {path.name for path in RUNS_DIR.iterdir()} if RUNS_DIR.exists() else set()
    adapter = StubOverpassAdapter(
        [
            SourceCandidate(
                office_name="Veldhoven Wonen",
                website="https://www.veldhovenwonen.nl",
                root_domain="veldhovenwonen.nl",
                raw_place="Veldhoven",
                normalized_place="Veldhoven",
                gemeente="Veldhoven",
                plaats="Veldhoven",
                place_status="current_gemeente",
                provincie="Noord-Brabant",
                source_adapter="overpass",
                source_origin="overpass_osm",
                confidence=0.50,
                needs_review=True,
                review_reason="overpass candidate requires validation",
            ),
            SourceCandidate(
                office_name="No Site Valkenswaard",
                raw_place="Valkenswaard",
                normalized_place="Valkenswaard",
                gemeente="Valkenswaard",
                plaats="Valkenswaard",
                place_status="current_gemeente",
                provincie="Noord-Brabant",
                source_adapter="overpass",
                source_origin="overpass_osm",
                confidence=0.50,
                needs_review=True,
                review_reason="overpass candidate requires validation",
            ),
        ]
    )

    output = run_discovery(
        province="noord-brabant",
        mode="full",
        max_queries=500,
        max_sites=1500,
        overpass_adapter=adapter,
    )

    try:
        assert output.report_path.exists()
        assert (output.run_dir / "candidate_domains.csv").exists()
        assert (output.run_dir / "discovered_sources.csv").exists()
        assert (output.run_dir / "rejected_candidates.csv").exists()
        assert (output.run_dir / "generated_queries.csv").exists()
        assert (LATEST_DIR / "candidate_domains.csv").exists()

        report_text = output.report_path.read_text(encoding="utf-8")
        assert "Free external discovery enabled: true" in report_text
        assert "Overpass status: ok" in report_text
        assert "Overpass raw candidates: 2" in report_text
        assert "Overpass candidates with website: 1" in report_text
        assert "Overpass candidates without website: 1" in report_text
        assert "Overpass Place Normalization Summary" in report_text
        assert "Overpass unmapped places" in report_text
        assert "Coverage By Gemeente" in report_text
        assert "Missing Expected Gemeenten After Overpass" in report_text
        assert "Expected gemeenten with rejected-only candidates" in report_text
        assert "Expected gemeenten still with zero candidates" in report_text

        assert (
            output.analyzed_candidates_count
            == output.discovered_sources_count
            + output.rejected_candidates_count
            + output.deduped_candidates_count
            + output.skipped_candidates_count
        )

        with (output.run_dir / "candidate_domains.csv").open("r", encoding="utf-8", newline="") as handle:
            candidate_rows = list(csv.DictReader(handle))
        assert any(row["source_origin"] == "overpass_osm" for row in candidate_rows)
        assert any(row["raw_place"] == "Veldhoven" for row in candidate_rows)
        assert any(row["normalized_place"] == "Veldhoven" for row in candidate_rows)
        assert any(row["place_status"] for row in candidate_rows)

        with (output.run_dir / "rejected_candidates.csv").open("r", encoding="utf-8", newline="") as handle:
            rejected_rows = list(csv.DictReader(handle))
        assert any(row["rejection_reason"] == "missing_website" for row in rejected_rows)

        with (output.run_dir / "generated_queries.csv").open("r", encoding="utf-8", newline="") as handle:
            query_rows = list(csv.DictReader(handle))
        assert any(row["gemeente"] == "Veldhoven" for row in query_rows)
    finally:
        _cleanup_output(output)
        remaining = {path.name for path in RUNS_DIR.iterdir()} if RUNS_DIR.exists() else set()
        assert remaining == before


def test_overpass_duplicate_merges_source_origin() -> None:
    before = {path.name for path in RUNS_DIR.iterdir()} if RUNS_DIR.exists() else set()
    adapter = StubOverpassAdapter(
        [
            SourceCandidate(
                office_name="Broeders OSM",
                website="https://www.broedersmakelaardij.nl",
                root_domain="broedersmakelaardij.nl",
                raw_place="Alphen-Chaam",
                normalized_place="Alphen-Chaam",
                gemeente="Alphen-Chaam",
                plaats="Alphen-Chaam",
                place_status="current_gemeente",
                provincie="Noord-Brabant",
                source_adapter="overpass",
                source_origin="overpass_osm",
                confidence=0.50,
                needs_review=True,
                review_reason="overpass candidate requires validation",
                osm_id="999",
            )
        ]
    )

    output = run_discovery(
        province="noord-brabant",
        mode="full",
        max_queries=50,
        max_sites=1500,
        overpass_adapter=adapter,
    )

    try:
        with (output.run_dir / "discovered_sources.csv").open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        merged = [row for row in rows if row["root_domain"] == "broedersmakelaardij.nl"]
        assert merged
        assert any(row["source_origin"] == "seed+overpass_osm" for row in merged)
        assert output.overpass_duplicates_vs_seed >= 1
    finally:
        _cleanup_output(output)
        remaining = {path.name for path in RUNS_DIR.iterdir()} if RUNS_DIR.exists() else set()
        assert remaining == before


def test_skip_overpass_uses_seed_only() -> None:
    before = {path.name for path in RUNS_DIR.iterdir()} if RUNS_DIR.exists() else set()

    output = run_discovery(
        province="noord-brabant",
        mode="full",
        max_queries=50,
        max_sites=20,
        skip_overpass=True,
    )

    try:
        report_text = output.report_path.read_text(encoding="utf-8")
        assert output.overpass_status == "skipped_cli"
        assert output.external_candidates_found == 0
        assert "Free external discovery enabled: false" in report_text
        assert "Overpass status: skipped_cli" in report_text
    finally:
        _cleanup_output(output)
        remaining = {path.name for path in RUNS_DIR.iterdir()} if RUNS_DIR.exists() else set()
        assert remaining == before
