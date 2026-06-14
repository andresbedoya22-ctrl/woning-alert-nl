from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

import pytest

from domek_wonen.discovery.discovery_artifacts import resolve_makelaar_sources_master


def test_resolve_makelaar_sources_master_uses_explicit_existing_input(tmp_path: Path) -> None:
    input_path = tmp_path / "custom_master.csv"
    input_path.write_text("source_id\nalpha\n", encoding="utf-8")

    assert resolve_makelaar_sources_master(input_path=input_path) == input_path


def test_resolve_makelaar_sources_master_uses_latest_when_present(tmp_path: Path, monkeypatch) -> None:
    latest_path = tmp_path / "data" / "discovery" / "latest" / "makelaar_sources_master.csv"
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.write_text("source_id\nlatest\n", encoding="utf-8")
    monkeypatch.setattr(
        "domek_wonen.discovery.discovery_artifacts.DEFAULT_MAKELAAR_SOURCES_MASTER_PATH",
        latest_path,
    )

    assert resolve_makelaar_sources_master() == latest_path


def test_resolve_makelaar_sources_master_restores_latest_from_latest_valid_run(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    latest_path = tmp_path / "data" / "discovery" / "latest" / "makelaar_sources_master.csv"
    runs_dir = tmp_path / "data" / "discovery" / "runs"
    older_valid_run = runs_dir / "20260614T080000Z"
    valid_run = runs_dir / "20260614T100000Z"
    invalid_run = runs_dir / "20260614T110000Z"

    older_valid_run.mkdir(parents=True, exist_ok=True)
    valid_run.mkdir(parents=True, exist_ok=True)
    invalid_run.mkdir(parents=True, exist_ok=True)
    (older_valid_run / "makelaar_sources_master.csv").write_text("old master", encoding="utf-8")
    (older_valid_run / "discovered_sources.csv").write_text("old discovered", encoding="utf-8")
    (valid_run / "makelaar_sources_master.csv").write_text("new master", encoding="utf-8")
    (valid_run / "discovered_sources.csv").write_text("new discovered", encoding="utf-8")
    (valid_run / "report.md").write_text("copied too", encoding="utf-8")
    (invalid_run / "makelaar_sources_master.csv").write_text("invalid only", encoding="utf-8")
    monkeypatch.setattr(
        "domek_wonen.discovery.discovery_artifacts.DEFAULT_MAKELAAR_SOURCES_MASTER_PATH",
        latest_path,
    )

    resolved = resolve_makelaar_sources_master(restore_latest=True)
    captured = capsys.readouterr()

    assert resolved == latest_path
    assert "restored discovery latest from run 20260614T100000Z" in captured.out
    assert latest_path.read_text(encoding="utf-8") == "new master"
    assert (latest_path.parent / "discovered_sources.csv").read_text(encoding="utf-8") == "new discovered"
    assert (latest_path.parent / "report.md").read_text(encoding="utf-8") == "copied too"


def test_resolve_makelaar_sources_master_raises_clear_error_when_missing_everywhere(
    tmp_path: Path, monkeypatch
) -> None:
    latest_path = tmp_path / "data" / "discovery" / "latest" / "makelaar_sources_master.csv"
    monkeypatch.setattr(
        "domek_wonen.discovery.discovery_artifacts.DEFAULT_MAKELAAR_SOURCES_MASTER_PATH",
        latest_path,
    )

    with pytest.raises(FileNotFoundError) as excinfo:
        resolve_makelaar_sources_master()

    message = str(excinfo.value)
    assert "scripts\\run_source_discovery.py" in message
    assert "makelaar_sources_master.csv" in message


def test_resolve_makelaar_sources_master_raises_clear_error_for_missing_explicit_input(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.csv"

    with pytest.raises(FileNotFoundError) as excinfo:
        resolve_makelaar_sources_master(input_path=missing_path)

    assert str(excinfo.value) == f"Input CSV not found: {missing_path}"
