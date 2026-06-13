from pathlib import Path
import csv
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.discovery.engine import LATEST_DIR, RUNS_DIR, run_discovery
from domek_wonen.discovery.models import SourceCandidate
from domek_wonen.discovery.overpass_adapter import OverpassDiscoveryResponse
from domek_wonen.discovery.website_fetcher import FetchResponse, WebsiteFetcher


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


class FixtureFetcher(WebsiteFetcher):
    def __init__(self, responses: dict[str, FetchResponse]) -> None:
        self.responses = {key.rstrip("/"): value for key, value in responses.items()}

    def fetch(self, url: str) -> FetchResponse:
        return self.responses.get(url.rstrip("/"), FetchResponse(url=url.rstrip("/"), status_code=404, text=""))


def _cleanup_output(output) -> None:
    if output.run_dir.exists():
        shutil.rmtree(output.run_dir)
    for filename in (
        "candidate_domains.csv",
        "discovered_sources.csv",
        "rejected_candidates.csv",
        "generated_queries.csv",
        "live_aanbod_attempts.csv",
        "aanbod_audit_results.csv",
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
        assert (output.run_dir / "live_aanbod_attempts.csv").exists()
        assert (output.run_dir / "aanbod_audit_results.csv").exists()
        assert (LATEST_DIR / "candidate_domains.csv").exists()
        assert (LATEST_DIR / "live_aanbod_attempts.csv").exists()
        assert (LATEST_DIR / "aanbod_audit_results.csv").exists()

        report_text = output.report_path.read_text(encoding="utf-8")
        assert "Free external discovery enabled: true" in report_text
        assert "Live aanbod enabled: false" in report_text
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
        assert "aanbod_detection_method" in candidate_rows[0]
        assert "aanbod_detection_score" in candidate_rows[0]
        assert "aanbod_validation_reason" in candidate_rows[0]
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


def test_live_aanbod_failure_does_not_break_engine(monkeypatch) -> None:
    before = {path.name for path in RUNS_DIR.iterdir()} if RUNS_DIR.exists() else set()
    monkeypatch.setattr("domek_wonen.discovery.engine.load_seed_candidates", lambda: [])
    adapter = StubOverpassAdapter(
        [
            SourceCandidate(
                office_name="Down Site",
                website="https://down.example.nl",
                root_domain="down.example.nl",
                raw_place="Breda",
                normalized_place="Breda",
                gemeente="Breda",
                plaats="Breda",
                place_status="current_gemeente",
                provincie="Noord-Brabant",
                source_adapter="overpass",
                source_origin="overpass_osm",
            )
        ]
    )
    fetcher = FixtureFetcher(
        {
            "https://down.example.nl": FetchResponse(
                url="https://down.example.nl",
                status_code=0,
                text="",
                error="connection refused",
            )
        }
    )

    output = run_discovery(
        province="noord-brabant",
        mode="full",
        max_queries=10,
        max_sites=10,
        overpass_adapter=adapter,
        live_aanbod=True,
        max_live_sites=10,
        website_fetcher=fetcher,
    )

    try:
        report_text = output.report_path.read_text(encoding="utf-8")
        assert output.live_sites_attempted >= 1
        assert output.live_sites_failed >= 1
        assert "Live aanbod enabled: true" in report_text
        assert "Live sites failed:" in report_text
        assert "Top failed domains" in report_text
        assert output.report_path.exists()
        with (output.run_dir / "live_aanbod_attempts.csv").open("r", encoding="utf-8", newline="") as handle:
            attempts = list(csv.DictReader(handle))
        assert attempts
        failure_rows = [row for row in attempts if row["root_domain"] == "down.example.nl"]
        assert failure_rows
        assert failure_rows[0]["final_status"] == "failed_fetch"
        assert "down.example.nl" in report_text
    finally:
        _cleanup_output(output)
        remaining = {path.name for path in RUNS_DIR.iterdir()} if RUNS_DIR.exists() else set()
        assert remaining == before


def test_live_aanbod_metrics_match_attempt_log(monkeypatch) -> None:
    before = {path.name for path in RUNS_DIR.iterdir()} if RUNS_DIR.exists() else set()
    monkeypatch.setattr("domek_wonen.discovery.engine.load_seed_candidates", lambda: [])
    adapter = StubOverpassAdapter(
        [
            SourceCandidate(
                office_name="Valid Site",
                website="https://valid.example.nl",
                root_domain="valid.example.nl",
                raw_place="Breda",
                normalized_place="Breda",
                gemeente="Breda",
                plaats="Breda",
                place_status="current_gemeente",
                provincie="Noord-Brabant",
                source_adapter="overpass",
                source_origin="overpass_osm",
            ),
            SourceCandidate(
                office_name="Suspect Site",
                website="https://suspect.example.nl",
                root_domain="suspect.example.nl",
                raw_place="Tilburg",
                normalized_place="Tilburg",
                gemeente="Tilburg",
                plaats="Tilburg",
                place_status="current_gemeente",
                provincie="Noord-Brabant",
                source_adapter="overpass",
                source_origin="overpass_osm",
            ),
            SourceCandidate(
                office_name="Existing Valid",
                website="https://kept.example.nl",
                root_domain="kept.example.nl",
                raw_place="Eindhoven",
                normalized_place="Eindhoven",
                gemeente="Eindhoven",
                plaats="Eindhoven",
                place_status="current_gemeente",
                provincie="Noord-Brabant",
                aanbod_url="https://kept.example.nl/aanbod",
                source_adapter="overpass",
                source_origin="overpass_osm",
            ),
        ]
    )
    homepage_html = '<html><body><a href="/aanbod">Aanbod</a></body></html>'
    suspect_html = "<html><body><h1>Aanbod</h1></body></html>"
    valid_html = (Path(__file__).resolve().parent / "fixtures" / "discovery" / "aanbod_listing_page.html").read_text(encoding="utf-8")
    fetcher = FixtureFetcher(
        {
            "https://valid.example.nl": FetchResponse(url="https://valid.example.nl", status_code=200, text=homepage_html),
            "https://valid.example.nl/aanbod": FetchResponse(url="https://valid.example.nl/aanbod", status_code=200, text=valid_html),
            "https://valid.example.nl/sitemap.xml": FetchResponse(url="https://valid.example.nl/sitemap.xml", status_code=404, text=""),
            "https://suspect.example.nl": FetchResponse(url="https://suspect.example.nl", status_code=200, text=homepage_html),
            "https://suspect.example.nl/aanbod": FetchResponse(url="https://suspect.example.nl/aanbod", status_code=200, text=suspect_html),
            "https://suspect.example.nl/sitemap.xml": FetchResponse(url="https://suspect.example.nl/sitemap.xml", status_code=404, text=""),
        }
    )

    output = run_discovery(
        province="noord-brabant",
        mode="full",
        max_queries=10,
        max_sites=10,
        overpass_adapter=adapter,
        live_aanbod=True,
        max_live_sites=10,
        website_fetcher=fetcher,
    )

    try:
        with (output.run_dir / "live_aanbod_attempts.csv").open("r", encoding="utf-8", newline="") as handle:
            attempts = list(csv.DictReader(handle))
        attempted = [row for row in attempts if row["attempted"] == "true"]
        successes = [row for row in attempted if row["final_status"] in {"valid", "suspect"}]
        skipped = [row for row in attempts if row["root_domain"] == "kept.example.nl" and row["final_status"] == "skipped_existing_valid"]
        assert output.live_sites_attempted == len(attempted)
        assert output.live_sites_success == len(successes)
        assert output.live_sites_failed == len(attempted) - len(successes)
        assert len(skipped) == 1
        assert skipped[0]["attempted"] == "false"
    finally:
        _cleanup_output(output)
        remaining = {path.name for path in RUNS_DIR.iterdir()} if RUNS_DIR.exists() else set()
        assert remaining == before


def test_live_aanbod_zero_limit_creates_csv_without_breaking(monkeypatch) -> None:
    before = {path.name for path in RUNS_DIR.iterdir()} if RUNS_DIR.exists() else set()
    monkeypatch.setattr("domek_wonen.discovery.engine.load_seed_candidates", lambda: [])
    adapter = StubOverpassAdapter([])

    output = run_discovery(
        province="noord-brabant",
        mode="full",
        max_queries=10,
        max_sites=10,
        overpass_adapter=adapter,
        live_aanbod=True,
        max_live_sites=0,
    )

    try:
        assert output.live_sites_attempted == 0
        assert (output.run_dir / "live_aanbod_attempts.csv").exists()
        with (output.run_dir / "live_aanbod_attempts.csv").open("r", encoding="utf-8", newline="") as handle:
            attempts = list(csv.DictReader(handle))
        assert attempts == []
    finally:
        _cleanup_output(output)
        remaining = {path.name for path in RUNS_DIR.iterdir()} if RUNS_DIR.exists() else set()
        assert remaining == before


def test_audit_aanbod_zero_limit_creates_csv_without_breaking(monkeypatch) -> None:
    before = {path.name for path in RUNS_DIR.iterdir()} if RUNS_DIR.exists() else set()
    monkeypatch.setattr("domek_wonen.discovery.engine.load_seed_candidates", lambda: [])
    adapter = StubOverpassAdapter(
        [
            SourceCandidate(
                office_name="Audit Candidate",
                website="https://audit.example.nl",
                root_domain="audit.example.nl",
                raw_place="Breda",
                normalized_place="Breda",
                gemeente="Breda",
                plaats="Breda",
                place_status="current_gemeente",
                provincie="Noord-Brabant",
                aanbod_url_quality="missing",
                source_adapter="overpass",
                source_origin="overpass_osm",
            )
        ]
    )

    output = run_discovery(
        province="noord-brabant",
        mode="full",
        max_queries=10,
        max_sites=10,
        overpass_adapter=adapter,
        audit_aanbod=True,
        max_audited_sites=0,
    )

    try:
        assert (output.run_dir / "aanbod_audit_results.csv").exists()
        with (output.run_dir / "aanbod_audit_results.csv").open("r", encoding="utf-8", newline="") as handle:
            attempts = list(csv.DictReader(handle))
        assert attempts == []
    finally:
        _cleanup_output(output)
        remaining = {path.name for path in RUNS_DIR.iterdir()} if RUNS_DIR.exists() else set()
        assert remaining == before


def test_report_includes_browser_audit_summary(monkeypatch) -> None:
    before = {path.name for path in RUNS_DIR.iterdir()} if RUNS_DIR.exists() else set()
    monkeypatch.setattr("domek_wonen.discovery.engine.load_seed_candidates", lambda: [])
    adapter = StubOverpassAdapter(
        [
            SourceCandidate(
                office_name="Audit Candidate",
                website="https://audit.example.nl",
                root_domain="audit.example.nl",
                raw_place="Breda",
                normalized_place="Breda",
                gemeente="Breda",
                plaats="Breda",
                place_status="current_gemeente",
                provincie="Noord-Brabant",
                aanbod_url_quality="missing",
                source_adapter="overpass",
                source_origin="overpass_osm",
            ),
            SourceCandidate(
                office_name="Audit Candidate 2",
                website="https://audit.example.nl",
                root_domain="audit.example.nl",
                raw_place="Tilburg",
                normalized_place="Tilburg",
                gemeente="Tilburg",
                plaats="Tilburg",
                place_status="current_gemeente",
                provincie="Noord-Brabant",
                aanbod_url_quality="missing",
                source_adapter="overpass",
                source_origin="overpass_osm",
            )
        ]
    )

    class StubAuditor:
        def __init__(self, *, confidence_threshold: int) -> None:
            self.confidence_threshold = confidence_threshold

        def audit_candidates(self, candidates, *, max_audited_sites):
            from domek_wonen.discovery.models import AanbodAuditAttempt

            attempts = []
            for index, candidate in enumerate(candidates[:2]):
                candidate.aanbod_url = "https://audit.example.nl/aanbod"
                candidate.aanbod_url_quality = "valid"
                candidate.aanbod_detection_method = "browser_audit"
                candidate.aanbod_detection_score = 91 - index
                candidate.aanbod_validation_reason = "residential_listing_index"
                candidate.needs_review = False
                attempts.append(AanbodAuditAttempt(
                    office_name=candidate.office_name,
                    website=candidate.website,
                    root_domain=candidate.root_domain,
                    gemeente=candidate.gemeente,
                    final_status="valid",
                    final_aanbod_url="https://audit.example.nl/aanbod",
                    confidence=91 - index,
                    detection_method="homepage_link",
                    homepage_status=200,
                    homepage_title="Aanbod",
                    candidates_found_count=3,
                    candidates_tested_count=1,
                    best_candidate_url="https://audit.example.nl/aanbod",
                    final_page_type="listing_index",
                    listing_signals_count=4,
                    residential_signals_count=5,
                    commercial_signals_count=0,
                    elapsed_ms=12,
                    residential_signals_found=["woning", "vraagprijs"],
                    commercial_signals_found=[],
                    page_quality_reason="residential_listing_index",
                    listing_signals_found=["vraagprijs", "woonoppervlakte"],
                    commercial_hard_block=False,
                    commercial_block_reason="",
                    is_duplicate_audit_result=index == 1,
                    rejection_reason="",
                ))
            return attempts

    monkeypatch.setattr("domek_wonen.discovery.engine.AanbodAuditor", StubAuditor)

    output = run_discovery(
        province="noord-brabant",
        mode="full",
        max_queries=10,
        max_sites=10,
        overpass_adapter=adapter,
        audit_aanbod=True,
        max_audited_sites=5,
    )

    try:
        report_text = output.report_path.read_text(encoding="utf-8")
        assert "## Aanbod Auditor Summary" in report_text
        assert "Audit aanbod enabled: true" in report_text
        assert "Audited sites count: 2" in report_text
        assert "Browser audit valid found: 2" in report_text
        assert "Browser audit unique valid domains: 1" in report_text
        assert "Browser audit duplicate valid rows: 1" in report_text
        assert "Valid aanbod_url after audit:" in report_text
        with (output.run_dir / "aanbod_audit_results.csv").open("r", encoding="utf-8", newline="") as handle:
            attempts = list(csv.DictReader(handle))
        assert len(attempts) == 2
        assert attempts[1]["is_duplicate_audit_result"] == "true"
    finally:
        _cleanup_output(output)
        remaining = {path.name for path in RUNS_DIR.iterdir()} if RUNS_DIR.exists() else set()
        assert remaining == before
