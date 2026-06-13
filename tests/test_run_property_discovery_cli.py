from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.properties.models import PropertyDiscoveryRunOutput
from scripts.run_property_discovery import main, parse_args


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
        ],
    )

    args = parse_args()

    assert args.province == "noord-brabant"
    assert args.max_sources == 20
    assert args.max_properties_per_source == 50


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

    calls: list[tuple[str, int, int]] = []

    def fake_runner(*, province: str, max_sources: int, max_properties_per_source: int):
        calls.append((province, max_sources, max_properties_per_source))
        return PropertyDiscoveryRunOutput(
            run_id="20260613T000000Z",
            run_dir=tmp_path,
            latest_dir=tmp_path,
            report_path=tmp_path / "property_discovery_report.md",
            sources_loaded=0,
            sources_attempted=0,
            sources_succeeded=0,
            sources_failed=0,
            total_property_candidates=0,
            deduped_properties=0,
        )

    monkeypatch.setattr("scripts.run_property_discovery.run_property_discovery", fake_runner)

    exit_code = main()

    assert exit_code == 0
    assert calls == [("noord-brabant", 0, 50)]
