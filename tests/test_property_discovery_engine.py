from pathlib import Path
import csv
import json
import subprocess
import sys
from dataclasses import asdict

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.properties.models import PropertyCandidate, PropertySource
from domek_wonen.properties.property_discovery_engine import REPORT_FILENAME, restore_latest_discovery_if_missing, run_property_discovery
from scripts.property_discovery_worker import run_worker


def _source(*, office_name: str = "Official One", root_domain: str = "example.nl", aanbod_url: str = "https://example.nl/aanbod") -> PropertySource:
    return PropertySource(
        source_id=root_domain,
        office_name=office_name,
        root_domain=root_domain,
        website=f"https://{root_domain}",
        aanbod_url=aanbod_url,
        gemeente="Breda",
        province="Noord-Brabant",
        legal_status="allowed_official_source",
        aanbod_url_quality="valid",
        is_active=True,
    )


def _candidate(*, property_url: str, classification: str) -> PropertyCandidate:
    return PropertyCandidate(
        source_id="example.nl",
        source_url="https://example.nl/aanbod",
        root_domain="example.nl",
        gemeente="Breda",
        property_url=property_url,
        property_url_classification=classification,
        title="Example",
    )


def _completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["worker"], returncode=returncode, stdout=stdout, stderr=stderr)


def _payload_from_fixture_html(source: PropertySource, fixture_html: str) -> dict[str, object]:
    from domek_wonen.properties.property_card_extractor import PropertyCardExtractor
    from domek_wonen.properties.property_discovery_engine import _annotate_candidate, _normalize_candidate
    from domek_wonen.properties.property_url_classifier import PropertyUrlClassifier

    candidates = [
        _annotate_candidate(_normalize_candidate(candidate), PropertyUrlClassifier())
        for candidate in PropertyCardExtractor().extract(fixture_html, source, source.aanbod_url)
    ]
    return {
        "status": "succeeded",
        "properties": [asdict(candidate) for candidate in candidates if candidate.property_url_classification == "property_detail_candidate"],
        "rejected": [asdict(candidate) for candidate in candidates if candidate.property_url_classification != "property_detail_candidate"],
        "errors": [],
        "duration_seconds": 0.01,
    }


def test_property_discovery_engine_handles_zero_max_sources_without_browser(tmp_path: Path) -> None:
    csv_path = tmp_path / "sources.csv"
    csv_path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website,gemeente,province,source_origin,aanbod_url,aanbod_url_quality,confidence_score,needs_review,review_reason,legal_status,last_seen_at,last_audited_at,is_active",
                "ok-1,Official One,official-one.nl,https://official-one.nl,Breda,Noord-Brabant,seed,https://official-one.nl/aanbod,valid,80,false,,allowed_official_source,20260613T000000Z,,true",
            ]
        ),
        encoding="utf-8",
    )

    output = run_property_discovery(
        province="noord-brabant",
        max_sources=0,
        max_properties_per_source=50,
        source_csv_path=csv_path,
        runs_base_dir=tmp_path / "runs",
        latest_dir=tmp_path / "latest",
    )

    assert output.sources_loaded == 0
    assert output.sources_attempted == 0
    assert output.run_status == "completed"
    assert (output.run_dir / "property_candidates.csv").exists()
    assert (output.latest_dir / "property_inventory.csv").exists()
    assert (output.run_dir / REPORT_FILENAME).exists()


def test_property_discovery_engine_filters_noise_from_inventory(tmp_path: Path, monkeypatch) -> None:
    csv_path = tmp_path / "sources.csv"
    csv_path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website,gemeente,province,source_origin,aanbod_url,aanbod_url_quality,confidence_score,needs_review,review_reason,legal_status,last_seen_at,last_audited_at,is_active",
                "ok-1,Official One,example.nl,https://example.nl,Breda,Noord-Brabant,seed,https://example.nl/aanbod,valid,80,false,,allowed_official_source,20260613T000000Z,,true",
            ]
        ),
        encoding="utf-8",
    )

    fixture_path = BASE_DIR / "tests" / "fixtures" / "properties" / "listing_page_with_noise.html"
    fixture_html = fixture_path.read_text(encoding="utf-8")

    def fake_worker(**kwargs):
        source = kwargs["source"]
        output_path = kwargs["output_path"]
        output_path.write_text(json.dumps(_payload_from_fixture_html(source, fixture_html)), encoding="utf-8")
        return _completed()

    monkeypatch.setattr("domek_wonen.properties.property_discovery_engine._run_source_worker_subprocess", fake_worker)

    output = run_property_discovery(
        province="noord-brabant",
        max_sources=1,
        max_properties_per_source=50,
        source_csv_path=csv_path,
        runs_base_dir=tmp_path / "runs",
        latest_dir=tmp_path / "latest",
    )

    with (output.run_dir / "property_inventory.csv").open("r", encoding="utf-8", newline="") as handle:
        inventory_rows = list(csv.DictReader(handle))
    with (output.run_dir / "property_rejected.csv").open("r", encoding="utf-8", newline="") as handle:
        rejected_rows = list(csv.DictReader(handle))

    assert [row["property_url"] for row in inventory_rows] == ["https://example.nl/aanbod/moleneindplein-163-7189"]
    assert any(row["property_url"] == "https://example.nl/diensten/aankoopmakelaar" for row in rejected_rows)
    assert all("/contact" not in row["property_url"] for row in inventory_rows)


def test_property_discovery_engine_continues_after_source_error_and_writes_report(tmp_path: Path, monkeypatch) -> None:
    csv_path = tmp_path / "sources.csv"
    csv_path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website,gemeente,province,source_origin,aanbod_url,aanbod_url_quality,confidence_score,needs_review,review_reason,legal_status,last_seen_at,last_audited_at,is_active",
                "bad-1,Bad One,bad-one.nl,https://bad-one.nl,Breda,Noord-Brabant,seed,https://bad-one.nl/aanbod,valid,80,false,,allowed_official_source,20260613T000000Z,,true",
                "ok-2,Good Two,example.nl,https://example.nl,Breda,Noord-Brabant,seed,https://example.nl/aanbod,valid,80,false,,allowed_official_source,20260613T000000Z,,true",
            ]
        ),
        encoding="utf-8",
    )

    fixture_path = BASE_DIR / "tests" / "fixtures" / "properties" / "listing_page_with_noise.html"
    fixture_html = fixture_path.read_text(encoding="utf-8")
    calls = {"count": 0}

    def fake_worker(**kwargs):
        calls["count"] += 1
        output_path = kwargs["output_path"]
        if calls["count"] == 1:
            output_path.write_text(
                json.dumps({"status": "failed", "properties": [], "rejected": [], "errors": ["boom"], "duration_seconds": 0.01}),
                encoding="utf-8",
            )
            return _completed(returncode=1, stderr="boom")
        source = kwargs["source"]
        output_path.write_text(json.dumps(_payload_from_fixture_html(source, fixture_html)), encoding="utf-8")
        return _completed()

    monkeypatch.setattr("domek_wonen.properties.property_discovery_engine._run_source_worker_subprocess", fake_worker)

    output = run_property_discovery(
        province="noord-brabant",
        max_sources=2,
        max_properties_per_source=10,
        source_csv_path=csv_path,
        runs_base_dir=tmp_path / "runs",
        latest_dir=tmp_path / "latest",
    )

    report_text = output.report_path.read_text(encoding="utf-8")

    assert output.sources_attempted == 2
    assert output.sources_failed == 1
    assert output.sources_succeeded == 1
    assert output.run_status == "completed_with_errors"
    assert "bad-1" in report_text
    assert (output.run_dir / "matching_ready_inventory.csv").exists()
    assert (output.run_dir / REPORT_FILENAME).exists()


def test_property_discovery_engine_continues_after_source_timeout(tmp_path: Path, monkeypatch) -> None:
    csv_path = tmp_path / "sources.csv"
    csv_path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website,gemeente,province,source_origin,aanbod_url,aanbod_url_quality,confidence_score,needs_review,review_reason,legal_status,last_seen_at,last_audited_at,is_active",
                "slow-1,Slow One,slow-one.nl,https://slow-one.nl,Breda,Noord-Brabant,seed,https://slow-one.nl/aanbod,valid,80,false,,allowed_official_source,20260613T000000Z,,true",
                "ok-2,Good Two,example.nl,https://example.nl,Breda,Noord-Brabant,seed,https://example.nl/aanbod,valid,80,false,,allowed_official_source,20260613T000000Z,,true",
            ]
        ),
        encoding="utf-8",
    )

    fixture_path = BASE_DIR / "tests" / "fixtures" / "properties" / "listing_page_with_noise.html"
    fixture_html = fixture_path.read_text(encoding="utf-8")
    calls = {"count": 0}

    def fake_worker(**kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise subprocess.TimeoutExpired(cmd=["worker"], timeout=kwargs["source_timeout_seconds"])
        source = kwargs["source"]
        kwargs["output_path"].write_text(json.dumps(_payload_from_fixture_html(source, fixture_html)), encoding="utf-8")
        return _completed()

    monkeypatch.setattr("domek_wonen.properties.property_discovery_engine._run_source_worker_subprocess", fake_worker)

    output = run_property_discovery(
        province="noord-brabant",
        max_sources=2,
        max_properties_per_source=10,
        source_csv_path=csv_path,
        runs_base_dir=tmp_path / "runs",
        latest_dir=tmp_path / "latest",
        source_timeout_seconds=0,
    )

    report_text = output.report_path.read_text(encoding="utf-8")

    assert output.sources_attempted == 2
    assert output.sources_timeout >= 1
    assert output.run_status == "completed_with_errors"
    assert "source timeout after 0s" in report_text


def test_property_discovery_engine_fails_cleanly_when_source_master_is_missing(tmp_path: Path, capsys) -> None:
    missing_path = tmp_path / "latest" / "makelaar_sources_master.csv"

    output = run_property_discovery(
        province="noord-brabant",
        max_sources=1,
        max_properties_per_source=1,
        source_csv_path=missing_path,
        runs_base_dir=tmp_path / "runs",
        latest_dir=tmp_path / "property_latest",
    )

    captured = capsys.readouterr()
    report_text = output.report_path.read_text(encoding="utf-8")

    assert output.run_status == "failed_missing_sources"
    assert "ERROR missing source file:" in captured.out
    assert "makelaar_sources_master.csv" in captured.out
    assert "scripts\\build_source_master.py" in captured.out
    assert "Traceback" not in (captured.out + captured.err)
    assert "- Run status: failed_missing_sources" in report_text
    assert "makelaar_sources_master.csv" in report_text


def test_restore_latest_discovery_if_missing_restores_from_latest_valid_run(tmp_path: Path, capsys) -> None:
    latest_dir = tmp_path / "discovery" / "latest"
    runs_dir = tmp_path / "discovery" / "runs"
    invalid_run = runs_dir / "20260614T090000Z"
    valid_run = runs_dir / "20260614T100000Z"
    older_valid_run = runs_dir / "20260614T080000Z"

    invalid_run.mkdir(parents=True, exist_ok=True)
    older_valid_run.mkdir(parents=True, exist_ok=True)
    valid_run.mkdir(parents=True, exist_ok=True)

    (older_valid_run / "discovered_sources.csv").write_text("old discovered", encoding="utf-8")
    (older_valid_run / "makelaar_sources_master.csv").write_text("old master", encoding="utf-8")
    (valid_run / "discovered_sources.csv").write_text("new discovered", encoding="utf-8")
    (valid_run / "makelaar_sources_master.csv").write_text("new master", encoding="utf-8")
    (valid_run / "report.md").write_text("copied too", encoding="utf-8")

    restored = restore_latest_discovery_if_missing(latest_dir / "makelaar_sources_master.csv")
    captured = capsys.readouterr()

    assert restored is True
    assert "restored discovery latest from run 20260614T100000Z" in captured.out
    assert (latest_dir / "makelaar_sources_master.csv").read_text(encoding="utf-8") == "new master"
    assert (latest_dir / "discovered_sources.csv").read_text(encoding="utf-8") == "new discovered"
    assert (latest_dir / "report.md").read_text(encoding="utf-8") == "copied too"


def test_property_discovery_engine_restores_latest_before_loading_sources(tmp_path: Path, monkeypatch, capsys) -> None:
    discovery_dir = tmp_path / "discovery"
    latest_dir = discovery_dir / "latest"
    valid_run = discovery_dir / "runs" / "20260614T100000Z"
    valid_run.mkdir(parents=True, exist_ok=True)
    csv_contents = "\n".join(
        [
            "source_id,office_name,root_domain,website,gemeente,province,source_origin,aanbod_url,aanbod_url_quality,confidence_score,score,needs_review,review_reason,legal_status,last_seen_at,last_audited_at,run_id,is_active",
            "ok-1,Official One,example.nl,https://example.nl,Breda,Noord-Brabant,source_discovery,https://example.nl/aanbod,valid,80,80,false,,allowed_official_source,20260613T000000Z,,run-1,true",
        ]
    )
    (valid_run / "makelaar_sources_master.csv").write_text(csv_contents, encoding="utf-8")
    (valid_run / "discovered_sources.csv").write_text("source_id\nok-1\n", encoding="utf-8")

    fixture_path = BASE_DIR / "tests" / "fixtures" / "properties" / "listing_page_with_noise.html"
    fixture_html = fixture_path.read_text(encoding="utf-8")

    def fake_worker(**kwargs):
        source = kwargs["source"]
        kwargs["output_path"].write_text(json.dumps(_payload_from_fixture_html(source, fixture_html)), encoding="utf-8")
        return _completed()

    monkeypatch.setattr("domek_wonen.properties.property_discovery_engine._run_source_worker_subprocess", fake_worker)

    output = run_property_discovery(
        province="noord-brabant",
        max_sources=1,
        max_properties_per_source=10,
        source_csv_path=latest_dir / "makelaar_sources_master.csv",
        runs_base_dir=tmp_path / "property-runs",
        latest_dir=tmp_path / "property-latest",
    )
    captured = capsys.readouterr()

    assert output.run_status == "completed"
    assert "restored discovery latest from run 20260614T100000Z" in captured.out
    assert (latest_dir / "makelaar_sources_master.csv").exists()
    assert (latest_dir / "discovered_sources.csv").exists()


def test_property_discovery_engine_fails_cleanly_without_latest_or_valid_runs(tmp_path: Path, capsys) -> None:
    discovery_dir = tmp_path / "discovery"
    latest_dir = discovery_dir / "latest"
    invalid_run = discovery_dir / "runs" / "20260614T100000Z"
    invalid_run.mkdir(parents=True, exist_ok=True)
    (invalid_run / "makelaar_sources_master.csv").write_text("incomplete", encoding="utf-8")

    output = run_property_discovery(
        province="noord-brabant",
        max_sources=1,
        max_properties_per_source=1,
        source_csv_path=latest_dir / "makelaar_sources_master.csv",
        runs_base_dir=tmp_path / "property-runs",
        latest_dir=tmp_path / "property-latest",
    )
    captured = capsys.readouterr()
    report_text = output.report_path.read_text(encoding="utf-8")

    assert output.run_status == "failed_missing_sources"
    assert "restored discovery latest from run" not in captured.out
    assert "ERROR missing source file:" in captured.out
    assert "makelaar_sources_master.csv" in report_text


def test_property_discovery_engine_smoke_uses_makelaar_sources_master_when_present(tmp_path: Path, monkeypatch) -> None:
    latest_dir = tmp_path / "discovery" / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)
    csv_path = latest_dir / "makelaar_sources_master.csv"
    csv_path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website,gemeente,province,source_origin,aanbod_url,aanbod_url_quality,confidence_score,score,needs_review,review_reason,legal_status,last_seen_at,last_audited_at,run_id,is_active",
                "ok-1,Official One,example.nl,https://example.nl,Breda,Noord-Brabant,source_discovery,https://example.nl/aanbod,valid,80,80,false,,allowed_official_source,20260613T000000Z,,run-1,true",
            ]
        ),
        encoding="utf-8",
    )

    fixture_path = BASE_DIR / "tests" / "fixtures" / "properties" / "listing_page_with_noise.html"
    fixture_html = fixture_path.read_text(encoding="utf-8")

    def fake_worker(**kwargs):
        source = kwargs["source"]
        kwargs["output_path"].write_text(json.dumps(_payload_from_fixture_html(source, fixture_html)), encoding="utf-8")
        return _completed()

    monkeypatch.setattr("domek_wonen.properties.property_discovery_engine._run_source_worker_subprocess", fake_worker)

    output = run_property_discovery(
        province="noord-brabant",
        max_sources=1,
        max_properties_per_source=50,
        source_csv_path=csv_path,
        runs_base_dir=tmp_path / "runs",
        latest_dir=tmp_path / "property_latest",
    )

    with (output.run_dir / "property_inventory.csv").open("r", encoding="utf-8", newline="") as handle:
        inventory_rows = list(csv.DictReader(handle))

    assert output.run_status == "completed"
    assert output.sources_loaded == 1
    assert len(inventory_rows) >= 1


def test_property_discovery_worker_writes_output_json_on_failure(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    input_path.write_text(
        json.dumps(
            {
                "office_name": "Broken Office",
                "website": "https://broken.example",
                "root_domain": "broken.example",
                "gemeente": "Breda",
                "province": "Noord-Brabant",
                "aanbod_url": "https://broken.example/aanbod",
                "max_properties_per_source": 5,
                "timeout_ms": 1000,
                "page_timeout_seconds": 1,
            }
        ),
        encoding="utf-8",
    )

    class FakeCrawler:
        def __init__(self, timeout_ms: int = 1000) -> None:
            self.timeout_ms = timeout_ms

        def __enter__(self) -> "FakeCrawler":
            raise RuntimeError("worker boom")

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    monkeypatch.setattr("scripts.property_discovery_worker.ListingPageCrawler", FakeCrawler)

    exit_code = run_worker(input_path, output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert payload["status"] == "failed"
    assert payload["properties"] == []
    assert payload["rejected"] == []
    assert payload["errors"] == ["worker boom"]


def test_property_discovery_worker_preserves_partial_candidates_when_detail_fails(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    input_path.write_text(
        json.dumps(
            {
                "office_name": "Detail Office",
                "website": "https://example.nl",
                "root_domain": "example.nl",
                "gemeente": "Breda",
                "province": "Noord-Brabant",
                "aanbod_url": "https://example.nl/aanbod",
                "max_properties_per_source": 5,
                "timeout_ms": 1000,
                "page_timeout_seconds": 1,
                "max_detail_pages": 3,
                "detail_timeout_seconds": 1,
            }
        ),
        encoding="utf-8",
    )

    class FakeCrawler:
        def __init__(self, timeout_ms: int = 1000) -> None:
            self.timeout_ms = timeout_ms

        def __enter__(self) -> "FakeCrawler":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def crawl(self, source):
            from domek_wonen.properties.models import CrawlResult

            return CrawlResult(source=source, ok=True, final_url=source.aanbod_url, html="<html></html>", error="", elapsed_ms=1)

    base_candidate = PropertyCandidate(
        source_id="example.nl",
        source_url="https://example.nl/aanbod",
        root_domain="example.nl",
        gemeente="Breda",
        property_url="https://example.nl/woningen/vier-heultjes-99-sprang-capelle",
        property_url_classification="property_detail_candidate",
        title="Example",
    )

    monkeypatch.setattr("scripts.property_discovery_worker.ListingPageCrawler", FakeCrawler)
    monkeypatch.setattr("scripts.property_discovery_worker.PropertyCardExtractor.extract", lambda self, html, source, source_url=None: [base_candidate])
    monkeypatch.setattr("scripts.property_discovery_worker._annotate_candidate", lambda candidate, url_classifier: candidate)
    monkeypatch.setattr("scripts.property_discovery_worker._normalize_candidate", lambda candidate: candidate)
    monkeypatch.setattr("scripts.property_discovery_worker._enrich_candidates", lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError("detail hung")))

    exit_code = run_worker(input_path, output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert payload["properties"]
    assert payload["status"] == "partial"
    assert payload["properties"][0]["property_url"] == "https://example.nl/woningen/vier-heultjes-99-sprang-capelle"
    assert payload["properties"][0]["detail_extraction_status"] == "pending"


def test_property_discovery_worker_disable_detail_extraction_keeps_cards_only(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    input_path.write_text(
        json.dumps(
            {
                "office_name": "Detail Office",
                "website": "https://example.nl",
                "root_domain": "example.nl",
                "gemeente": "Breda",
                "province": "Noord-Brabant",
                "aanbod_url": "https://example.nl/aanbod",
                "max_properties_per_source": 5,
                "timeout_ms": 1000,
                "page_timeout_seconds": 1,
                "disable_detail_extraction": True,
            }
        ),
        encoding="utf-8",
    )

    class FakeCrawler:
        def __init__(self, timeout_ms: int = 1000) -> None:
            self.timeout_ms = timeout_ms

        def __enter__(self) -> "FakeCrawler":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def crawl(self, source):
            from domek_wonen.properties.models import CrawlResult

            return CrawlResult(source=source, ok=True, final_url=source.aanbod_url, html="<html></html>", error="", elapsed_ms=1)

        def fetch(self, url, source, timeout_ms=None):
            raise AssertionError("detail fetch should not run when disabled")

    base_candidate = PropertyCandidate(
        source_id="example.nl",
        source_url="https://example.nl/aanbod",
        root_domain="example.nl",
        gemeente="Breda",
        property_url="https://example.nl/woningen/vier-heultjes-99-sprang-capelle",
        property_url_classification="property_detail_candidate",
        title="Example",
    )

    monkeypatch.setattr("scripts.property_discovery_worker.ListingPageCrawler", FakeCrawler)
    monkeypatch.setattr("scripts.property_discovery_worker.PropertyCardExtractor.extract", lambda self, html, source, source_url=None: [base_candidate])
    monkeypatch.setattr("scripts.property_discovery_worker._annotate_candidate", lambda candidate, url_classifier: candidate)
    monkeypatch.setattr("scripts.property_discovery_worker._normalize_candidate", lambda candidate: candidate)

    exit_code = run_worker(input_path, output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["status"] == "succeeded"
    assert payload["properties"][0]["detail_extraction_status"] == "skipped"


def test_property_discovery_engine_marks_timeout_and_continues(tmp_path: Path, monkeypatch) -> None:
    csv_path = tmp_path / "sources.csv"
    csv_path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website,gemeente,province,source_origin,aanbod_url,aanbod_url_quality,confidence_score,needs_review,review_reason,legal_status,last_seen_at,last_audited_at,is_active",
                "slow-1,Slow One,slow-one.nl,https://slow-one.nl,Breda,Noord-Brabant,seed,https://slow-one.nl/aanbod,valid,80,false,,allowed_official_source,20260613T000000Z,,true",
                "ok-2,Good Two,example.nl,https://example.nl,Breda,Noord-Brabant,seed,https://example.nl/aanbod,valid,80,false,,allowed_official_source,20260613T000000Z,,true",
            ]
        ),
        encoding="utf-8",
    )

    seen_sources: list[str] = []

    def fake_worker(**kwargs):
        source = kwargs["source"]
        seen_sources.append(source.source_id)
        if source.source_id == "slow-1":
            raise subprocess.TimeoutExpired(cmd=["worker"], timeout=kwargs["source_timeout_seconds"])
        kwargs["output_path"].write_text(
            json.dumps(
                {
                    "status": "succeeded",
                    "properties": [asdict(_candidate(property_url="https://example.nl/aanbod/1", classification="property_detail_candidate"))],
                    "rejected": [asdict(_candidate(property_url="https://example.nl/diensten/aankoopmakelaar", classification="other"))],
                    "errors": [],
                    "duration_seconds": 0.01,
                }
            ),
            encoding="utf-8",
        )
        return _completed()

    monkeypatch.setattr("domek_wonen.properties.property_discovery_engine._run_source_worker_subprocess", fake_worker)

    output = run_property_discovery(
        province="noord-brabant",
        max_sources=2,
        max_properties_per_source=10,
        source_csv_path=csv_path,
        runs_base_dir=tmp_path / "runs",
        latest_dir=tmp_path / "latest",
        source_timeout_seconds=1,
    )

    report_text = output.report_path.read_text(encoding="utf-8")

    assert seen_sources == ["slow-1", "ok-2"]
    assert output.sources_attempted == 2
    assert output.sources_timeout == 1
    assert output.sources_succeeded == 1
    assert output.run_status == "completed_with_errors"
    assert "source timeout after 1s" in report_text


def test_property_discovery_engine_preserves_partial_results_after_worker_timeout(tmp_path: Path, monkeypatch) -> None:
    csv_path = tmp_path / "sources.csv"
    csv_path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website,gemeente,province,source_origin,aanbod_url,aanbod_url_quality,confidence_score,needs_review,review_reason,legal_status,last_seen_at,last_audited_at,is_active",
                "slow-1,Slow One,slow-one.nl,https://slow-one.nl,Breda,Noord-Brabant,seed,https://slow-one.nl/aanbod,valid,80,false,,allowed_official_source,20260613T000000Z,,true",
            ]
        ),
        encoding="utf-8",
    )

    partial_payload = {
        "status": "partial",
        "properties": [asdict(_candidate(property_url="https://example.nl/aanbod/1", classification="property_detail_candidate"))],
        "rejected": [asdict(_candidate(property_url="https://example.nl/diensten/aankoopmakelaar", classification="other"))],
        "errors": [],
        "duration_seconds": 0.01,
    }

    def fake_worker(**kwargs):
        kwargs["output_path"].write_text(json.dumps(partial_payload), encoding="utf-8")
        raise subprocess.TimeoutExpired(cmd=["worker"], timeout=kwargs["source_timeout_seconds"])

    monkeypatch.setattr("domek_wonen.properties.property_discovery_engine._run_source_worker_subprocess", fake_worker)

    output = run_property_discovery(
        province="noord-brabant",
        max_sources=1,
        max_properties_per_source=10,
        source_csv_path=csv_path,
        runs_base_dir=tmp_path / "runs",
        latest_dir=tmp_path / "latest",
        source_timeout_seconds=1,
    )

    assert output.sources_attempted == 1
    assert output.sources_timeout == 1
    assert output.total_property_candidates == 2
    assert output.deduped_properties == 0


def test_property_discovery_engine_carredewit_like_partial_timeout_does_not_drop_to_zero(tmp_path: Path, monkeypatch) -> None:
    csv_path = tmp_path / "sources.csv"
    csv_path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website,gemeente,province,source_origin,aanbod_url,aanbod_url_quality,confidence_score,needs_review,review_reason,legal_status,last_seen_at,last_audited_at,is_active",
                "ok-1,Carre de Wit,example.nl,https://example.nl,Breda,Noord-Brabant,seed,https://example.nl/aanbod,valid,80,false,,allowed_official_source,20260613T000000Z,,true",
            ]
        ),
        encoding="utf-8",
    )
    fixture_path = BASE_DIR / "tests" / "fixtures" / "properties" / "listing_page_with_noise.html"
    fixture_html = fixture_path.read_text(encoding="utf-8")

    def fake_worker(**kwargs):
        source = kwargs["source"]
        kwargs["output_path"].write_text(
            json.dumps(
                {
                    **_payload_from_fixture_html(source, fixture_html),
                    "status": "partial",
                }
            ),
            encoding="utf-8",
        )
        raise subprocess.TimeoutExpired(cmd=["worker"], timeout=kwargs["source_timeout_seconds"])

    monkeypatch.setattr("domek_wonen.properties.property_discovery_engine._run_source_worker_subprocess", fake_worker)

    output = run_property_discovery(
        province="noord-brabant",
        max_sources=1,
        max_properties_per_source=3,
        source_csv_path=csv_path,
        runs_base_dir=tmp_path / "runs",
        latest_dir=tmp_path / "latest",
        source_timeout_seconds=1,
    )

    assert output.total_property_candidates > 0
    assert output.deduped_properties > 0


def test_property_discovery_inventory_marks_empty_address_for_review(tmp_path: Path, monkeypatch) -> None:
    csv_path = tmp_path / "sources.csv"
    csv_path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website,gemeente,province,source_origin,aanbod_url,aanbod_url_quality,confidence_score,needs_review,review_reason,legal_status,last_seen_at,last_audited_at,is_active",
                "ok-1,Official One,example.nl,https://example.nl,Breda,Noord-Brabant,seed,https://example.nl/aanbod,valid,80,false,,allowed_official_source,20260613T000000Z,,true",
            ]
        ),
        encoding="utf-8",
    )

    def fake_worker(**kwargs):
        kwargs["output_path"].write_text(
            json.dumps(
                {
                    "status": "succeeded",
                    "properties": [
                        {
                            **asdict(_candidate(property_url="https://example.nl/woningen/onbekend", classification="property_detail_candidate")),
                            "address_raw": "",
                            "city_raw": "",
                            "detail_extraction_status": "failed",
                            "detail_error": "detail page missing usable signals",
                        }
                    ],
                    "rejected": [],
                    "errors": [],
                    "duration_seconds": 0.01,
                }
            ),
            encoding="utf-8",
        )
        return _completed()

    monkeypatch.setattr("domek_wonen.properties.property_discovery_engine._run_source_worker_subprocess", fake_worker)

    output = run_property_discovery(
        province="noord-brabant",
        max_sources=1,
        max_properties_per_source=10,
        source_csv_path=csv_path,
        runs_base_dir=tmp_path / "runs",
        latest_dir=tmp_path / "latest",
    )

    with (output.run_dir / "property_inventory.csv").open("r", encoding="utf-8", newline="") as handle:
        inventory_rows = list(csv.DictReader(handle))
    with (output.run_dir / "rejected_property_candidates.csv").open("r", encoding="utf-8", newline="") as handle:
        rejected_rows = list(csv.DictReader(handle))

    assert inventory_rows == []
    assert len(rejected_rows) == 1
    assert rejected_rows[0]["address_raw"] == ""
    assert rejected_rows[0]["address_quality"] == "invalid"
    assert rejected_rows[0]["needs_review"] == "true"
    assert rejected_rows[0]["needs_review_reason"] == "invalid_address_raw"
    assert "missing address after detail extraction" in rejected_rows[0]["review_reason"]


def test_property_discovery_invalid_address_raw_uses_slug_fallback_and_stays_in_inventory(tmp_path: Path, monkeypatch) -> None:
    csv_path = tmp_path / "sources.csv"
    csv_path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website,gemeente,province,source_origin,aanbod_url,aanbod_url_quality,confidence_score,needs_review,review_reason,legal_status,last_seen_at,last_audited_at,is_active",
                "ok-1,Official One,example.nl,https://example.nl,Breda,Noord-Brabant,seed,https://example.nl/aanbod,valid,80,false,,allowed_official_source,20260613T000000Z,,true",
            ]
        ),
        encoding="utf-8",
    )

    def fake_worker(**kwargs):
        kwargs["output_path"].write_text(
            json.dumps(
                {
                    "status": "succeeded",
                    "properties": [
                        {
                            **asdict(
                                _candidate(
                                    property_url="https://example.nl/woningen/vier-heultjes-99-sprang-capelle",
                                    classification="property_detail_candidate",
                                )
                            ),
                            "address_raw": "k.k. Snel naar Aanbod Aankopen Verkopen",
                            "price_raw": "EUR 425.000 k.k.",
                            "status_raw": "beschikbaar",
                        }
                    ],
                    "rejected": [],
                    "errors": [],
                    "duration_seconds": 0.01,
                }
            ),
            encoding="utf-8",
        )
        return _completed()

    monkeypatch.setattr("domek_wonen.properties.property_discovery_engine._run_source_worker_subprocess", fake_worker)

    output = run_property_discovery(
        province="noord-brabant",
        max_sources=1,
        max_properties_per_source=10,
        source_csv_path=csv_path,
        runs_base_dir=tmp_path / "runs",
        latest_dir=tmp_path / "latest",
    )

    with (output.run_dir / "matching_ready_inventory.csv").open("r", encoding="utf-8", newline="") as handle:
        inventory_rows = list(csv.DictReader(handle))

    assert len(inventory_rows) == 1
    assert inventory_rows[0]["address_raw"] == "Vier Heultjes 99"
    assert inventory_rows[0]["city_raw"] == "Sprang-Capelle"
    assert inventory_rows[0]["address_quality"] == "valid"
    assert inventory_rows[0]["needs_review_reason"] == ""


def test_property_discovery_invalid_address_raw_is_excluded_from_matching_ready_and_sent_to_rejected(tmp_path: Path, monkeypatch) -> None:
    csv_path = tmp_path / "sources.csv"
    csv_path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website,gemeente,province,source_origin,aanbod_url,aanbod_url_quality,confidence_score,needs_review,review_reason,legal_status,last_seen_at,last_audited_at,is_active",
                "ok-1,Official One,example.nl,https://example.nl,Breda,Noord-Brabant,seed,https://example.nl/aanbod,valid,80,false,,allowed_official_source,20260613T000000Z,,true",
            ]
        ),
        encoding="utf-8",
    )

    def fake_worker(**kwargs):
        kwargs["output_path"].write_text(
            json.dumps(
                {
                    "status": "succeeded",
                    "properties": [
                        {
                            **asdict(
                                _candidate(
                                    property_url="https://example.nl/woningen/detail",
                                    classification="property_detail_candidate",
                                )
                            ),
                            "address_raw": "Diensten Verkoop Aankoop Taxatie Energielabel Snel naar Aanbod 123",
                            "price_raw": "EUR 410.000 k.k.",
                            "status_raw": "beschikbaar",
                        }
                    ],
                    "rejected": [],
                    "errors": [],
                    "duration_seconds": 0.01,
                }
            ),
            encoding="utf-8",
        )
        return _completed()

    monkeypatch.setattr("domek_wonen.properties.property_discovery_engine._run_source_worker_subprocess", fake_worker)

    output = run_property_discovery(
        province="noord-brabant",
        max_sources=1,
        max_properties_per_source=10,
        source_csv_path=csv_path,
        runs_base_dir=tmp_path / "runs",
        latest_dir=tmp_path / "latest",
    )

    with (output.run_dir / "matching_ready_inventory.csv").open("r", encoding="utf-8", newline="") as handle:
        inventory_rows = list(csv.DictReader(handle))
    with (output.run_dir / "rejected_property_candidates.csv").open("r", encoding="utf-8", newline="") as handle:
        rejected_rows = list(csv.DictReader(handle))

    assert inventory_rows == []
    assert len(rejected_rows) == 1
    assert rejected_rows[0]["property_url"] == "https://example.nl/woningen/detail"
    assert rejected_rows[0]["price_raw"] == "EUR 410.000 k.k."
    assert rejected_rows[0]["status_raw"] == "beschikbaar"
    assert rejected_rows[0]["address_quality"] == "invalid"
    assert rejected_rows[0]["needs_review"] == "true"
    assert rejected_rows[0]["needs_review_reason"] == "invalid_address_raw"
    assert "invalid address_raw after quality gate" in rejected_rows[0]["review_reason"]

    report_text = output.report_path.read_text(encoding="utf-8")
    assert "- Invalid address_raw: 1" in report_text
    assert "- Needs review: 1" in report_text
    assert "- Clean available properties: 0" in report_text


def test_property_discovery_engine_platform_realworks_filters_only_realworks_sources(tmp_path: Path, monkeypatch) -> None:
    csv_path = tmp_path / "sources.csv"
    fingerprint_path = tmp_path / "platform_fingerprint_results.csv"
    csv_path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website,gemeente,province,source_origin,aanbod_url,aanbod_url_quality,confidence_score,needs_review,review_reason,legal_status,last_seen_at,last_audited_at,is_active",
                "rw-1,Realworks Office,realworks-office.nl,https://realworks-office.nl,Breda,Noord-Brabant,seed,https://realworks-office.nl/aanbod,valid,80,false,,allowed_official_source,20260613T000000Z,,true",
                "custom-1,Custom Office,custom-office.nl,https://custom-office.nl,Breda,Noord-Brabant,seed,https://custom-office.nl/aanbod,valid,80,false,,allowed_official_source,20260613T000000Z,,true",
            ]
        ),
        encoding="utf-8",
    )
    fingerprint_path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website_url,aanbod_url,detected_platform,confidence,evidence,parser_priority,recommended_next_action,fetch_status,error",
                "rw-1,Realworks Office,realworks-office.nl,https://realworks-office.nl,https://realworks-office.nl/aanbod,realworks,0.95,signal,p1,bundle,homepage_ok,",
                "custom-1,Custom Office,custom-office.nl,https://custom-office.nl,https://custom-office.nl/aanbod,custom,0.55,signal,p3,defer,homepage_ok,",
            ]
        ),
        encoding="utf-8",
    )

    seen_sources: list[str] = []

    def fake_worker(**kwargs):
        source = kwargs["source"]
        seen_sources.append(source.source_id)
        kwargs["output_path"].write_text(
            json.dumps(
                {
                    "status": "succeeded",
                    "properties": [asdict(_candidate(property_url="https://realworks-office.nl/woningen/test-1-breda", classification="property_detail_candidate"))],
                    "rejected": [],
                    "errors": [],
                    "duration_seconds": 0.01,
                    "parser_info": {"parser_used": "realworks_parser", "realworks_parser_success": True},
                }
            ),
            encoding="utf-8",
        )
        return _completed()

    monkeypatch.setattr("domek_wonen.properties.property_discovery_engine._run_source_worker_subprocess", fake_worker)

    output = run_property_discovery(
        province="noord-brabant",
        max_sources=5,
        max_properties_per_source=10,
        source_csv_path=csv_path,
        runs_base_dir=tmp_path / "runs",
        latest_dir=tmp_path / "latest",
        platform="realworks",
        platform_fingerprint_input=fingerprint_path,
    )

    assert output.sources_loaded == 1
    assert seen_sources == ["rw-1"]


def test_property_discovery_worker_falls_back_to_generic_when_realworks_parser_fails(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    input_path.write_text(
        json.dumps(
            {
                "office_name": "Realworks Office",
                "website": "https://example.nl",
                "root_domain": "example.nl",
                "gemeente": "Breda",
                "province": "Noord-Brabant",
                "aanbod_url": "https://example.nl/aanbod/woningaanbod",
                "detected_platform": "realworks",
                "max_properties_per_source": 5,
                "timeout_ms": 1000,
                "page_timeout_seconds": 1,
                "max_detail_pages": 1,
                "detail_timeout_seconds": 1,
            }
        ),
        encoding="utf-8",
    )

    class FailingParser:
        def parse(self, source, *, max_properties_per_source: int, page_timeout_seconds: int):
            raise RuntimeError("realworks boom")

    class FakeCrawler:
        def __init__(self, timeout_ms: int = 1000) -> None:
            self.timeout_ms = timeout_ms

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def crawl(self, source):
            return type(
                "Result",
                (),
                {
                    "ok": True,
                    "html": "<html></html>",
                    "final_url": source.aanbod_url,
                    "error": "",
                },
            )()

        def fetch(self, url, source, timeout_ms=None):
            raise AssertionError("detail fetch should not run")

    base_candidate = PropertyCandidate(
        source_id="example.nl",
        source_url="https://example.nl/aanbod/woningaanbod",
        root_domain="example.nl",
        gemeente="Breda",
        property_url="https://example.nl/woningen/vier-heultjes-99-sprang-capelle",
        property_url_classification="property_detail_candidate",
        title="Example",
        address_raw="Vier Heultjes 99",
        city_raw="Sprang-Capelle",
        price_raw="EUR 425.000 k.k.",
    )

    monkeypatch.setattr("scripts.property_discovery_worker.get_platform_parser", lambda platform_name: FailingParser())
    monkeypatch.setattr("scripts.property_discovery_worker.ListingPageCrawler", FakeCrawler)
    monkeypatch.setattr("scripts.property_discovery_worker.PropertyCardExtractor.extract", lambda self, html, source, source_url=None: [base_candidate])
    monkeypatch.setattr("scripts.property_discovery_worker._annotate_candidate", lambda candidate, url_classifier: candidate)
    monkeypatch.setattr("scripts.property_discovery_worker._normalize_candidate", lambda candidate: candidate)

    exit_code = run_worker(input_path, output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["status"] == "succeeded"
    assert payload["parser_info"]["realworks_parser_failed"] is True
    assert payload["parser_info"]["parser_fallback_used"] is True
    assert payload["parser_info"]["generic_parser_success"] is True
    assert payload["parser_info"]["parser_used"] == "generic"


def test_property_discovery_rejected_candidates_skips_empty_rows(tmp_path: Path, monkeypatch) -> None:
    csv_path = tmp_path / "sources.csv"
    csv_path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website,gemeente,province,source_origin,aanbod_url,aanbod_url_quality,confidence_score,needs_review,review_reason,legal_status,last_seen_at,last_audited_at,is_active",
                "ok-1,Official One,example.nl,https://example.nl,Breda,Noord-Brabant,seed,https://example.nl/aanbod,valid,80,false,,allowed_official_source,20260613T000000Z,,true",
            ]
        ),
        encoding="utf-8",
    )

    def fake_worker(**kwargs):
        kwargs["output_path"].write_text(
            json.dumps(
                {
                    "status": "succeeded",
                    "properties": [],
                    "rejected": [
                        {
                            **asdict(_candidate(property_url="", classification="other")),
                            "review_reason": "",
                            "excluded_reason": "",
                            "property_url": "",
                        }
                    ],
                    "errors": [],
                    "duration_seconds": 0.01,
                }
            ),
            encoding="utf-8",
        )
        return _completed()

    monkeypatch.setattr("domek_wonen.properties.property_discovery_engine._run_source_worker_subprocess", fake_worker)

    output = run_property_discovery(
        province="noord-brabant",
        max_sources=1,
        max_properties_per_source=10,
        source_csv_path=csv_path,
        runs_base_dir=tmp_path / "runs",
        latest_dir=tmp_path / "latest",
    )

    with (output.run_dir / "rejected_property_candidates.csv").open("r", encoding="utf-8", newline="") as handle:
        rejected_rows = list(csv.DictReader(handle))

    assert rejected_rows == []


def test_property_discovery_skips_invalid_and_property_detail_sources_by_default(tmp_path: Path) -> None:
    latest_dir = tmp_path / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)
    csv_path = latest_dir / "makelaar_sources_master.csv"
    csv_path.write_text(
        "\n".join(
            [
                "source_id,office_name,root_domain,website,gemeente,province,source_origin,aanbod_url,aanbod_url_quality,aanbod_url_type,confidence_score,source_quality_status,source_quality_reason,needs_review,review_reason,legal_status,last_seen_at,last_audited_at,is_active",
                "ok-1,Official One,example.nl,https://example.nl,Breda,Noord-Brabant,seed,https://example.nl/aanbod,valid,listing_index,80,valid,,false,,allowed_official_source,20260613T000000Z,,true",
                "bad-1,Detail One,detail.nl,https://detail.nl,Breda,Noord-Brabant,seed,https://detail.nl/aanbod/woningaanbod/koop/huis-123-Markt-1,valid,property_detail,80,valid,,false,,allowed_official_source,20260613T000000Z,,true",
                "bad-2,Invalid One,invalid.nl,https://invalid.nl,Breda,Noord-Brabant,seed,https://invalid.nl/contact,valid,listing_index,80,invalid,aanbod_url_type=commercial_page,false,,allowed_official_source,20260613T000000Z,,true",
            ]
        ),
        encoding="utf-8",
    )

    output = run_property_discovery(
        province="noord-brabant",
        max_sources=10,
        max_properties_per_source=1,
        source_csv_path=csv_path,
        runs_base_dir=tmp_path / "runs",
        latest_dir=latest_dir,
        verbose=False,
    )

    assert output.sources_loaded == 1
    assert output.sources_skipped_invalid_aanbod_url == 2
    report_text = output.report_path.read_text(encoding="utf-8")
    assert "- Sources skipped invalid aanbod_url: 2" in report_text
