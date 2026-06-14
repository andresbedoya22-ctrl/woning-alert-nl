from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.properties.models import PropertyDiscoveryRunOutput
from scripts.run_property_discovery import DEFAULT_PLATFORM_FINGERPRINT_INPUT, _effective_options, main, parse_args


def _output(tmp_path: Path, run_status: str = "completed") -> PropertyDiscoveryRunOutput:
    return PropertyDiscoveryRunOutput(
        run_id="20260613T000000Z",
        run_dir=tmp_path,
        latest_dir=tmp_path,
        report_path=tmp_path / "property_discovery_run_report.md",
        run_status=run_status,
        started_at="2026-06-13T00:00:00+00:00",
        finished_at="2026-06-13T00:00:01+00:00",
        duration_seconds=1.0,
        sources_loaded=0,
        sources_attempted=0,
        sources_succeeded=0,
        sources_failed=0,
        sources_timeout=0,
        sources_skipped_invalid_aanbod_url=0,
        total_property_candidates=0,
        deduped_properties=0,
        rejected_candidates=0,
    )


def test_property_cli_parse_args(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_property_discovery.py",
            "--province",
            "noord-brabant",
            "--max-sources",
            "20",
            "--max-properties-per-source",
            "50",
            "--source-timeout-seconds",
            "90",
            "--page-timeout-seconds",
            "30",
            "--max-detail-pages",
            "3",
            "--detail-timeout-seconds",
            "10",
            "--disable-detail-extraction",
            "--platform",
            "realworks",
            "--platform-fingerprint-input",
            "custom-platforms.csv",
            "--disable-platform-parsers",
            "--include-invalid-sources",
            "--smoke",
        ],
    )

    args = parse_args()

    assert args.province == "noord-brabant"
    assert args.max_sources == 20
    assert args.max_properties_per_source == 50
    assert args.source_timeout_seconds == 90
    assert args.page_timeout_seconds == 30
    assert args.max_detail_pages == 3
    assert args.detail_timeout_seconds == 10
    assert args.disable_detail_extraction is True
    assert args.platform == "realworks"
    assert args.platform_fingerprint_input == Path("custom-platforms.csv")
    assert args.disable_platform_parsers is True
    assert args.include_invalid_sources is True
    assert args.smoke is True


def test_property_cli_main_supports_zero_max_sources(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_property_discovery.py",
            "--province",
            "noord-brabant",
            "--max-sources",
            "0",
            "--max-properties-per-source",
            "50",
        ],
    )

    calls: list[dict[str, int | bool | str]] = []

    def fake_runner(**kwargs):
        calls.append(kwargs)
        return _output(tmp_path)

    monkeypatch.setattr("scripts.run_property_discovery.run_property_discovery", fake_runner)

    exit_code = main()

    assert exit_code == 0
    assert calls == [
        {
            "province": "noord-brabant",
            "max_sources": 0,
            "max_properties_per_source": 50,
            "timeout_ms": 30000,
            "source_timeout_seconds": 90,
            "page_timeout_seconds": 30,
            "max_detail_pages": 3,
            "detail_timeout_seconds": 10,
            "disable_detail_extraction": False,
            "platform": "",
            "platform_fingerprint_input": DEFAULT_PLATFORM_FINGERPRINT_INPUT,
            "disable_platform_parsers": False,
            "include_invalid_sources": False,
            "verbose": True,
        }
    ]


def test_property_cli_smoke_defaults() -> None:
    args = parse_args(["--province", "noord-brabant", "--smoke"])
    options = _effective_options(args)

    assert options["max_sources"] == 1
    assert options["max_properties_per_source"] == 1
    assert options["source_timeout_seconds"] == 30
    assert options["page_timeout_seconds"] == 15
    assert options["max_detail_pages"] == 1
    assert options["detail_timeout_seconds"] == 5
    assert options["platform"] == ""
    assert options["platform_fingerprint_input"] == DEFAULT_PLATFORM_FINGERPRINT_INPUT
    assert options["disable_platform_parsers"] is False
    assert options["include_invalid_sources"] is False


def test_property_cli_returns_error_for_missing_sources(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_property_discovery.py",
            "--province",
            "noord-brabant",
        ],
    )

    def fake_runner(**kwargs):
        return _output(tmp_path, run_status="failed_missing_sources")

    monkeypatch.setattr("scripts.run_property_discovery.run_property_discovery", fake_runner)

    exit_code = main()

    assert exit_code == 1
