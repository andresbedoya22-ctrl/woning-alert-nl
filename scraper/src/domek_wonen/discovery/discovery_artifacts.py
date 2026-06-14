from __future__ import annotations

import shutil
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[4]
DEFAULT_MAKELAAR_SOURCES_MASTER_PATH = BASE_DIR / "data" / "discovery" / "latest" / "makelaar_sources_master.csv"
_REQUIRED_RUN_FILES = ("makelaar_sources_master.csv", "discovered_sources.csv")


def _log(message: str) -> None:
    print(f"[discovery-artifacts] {message}", flush=True)


def _is_valid_discovery_run(run_dir: Path) -> bool:
    return run_dir.is_dir() and all((run_dir / filename).exists() for filename in _REQUIRED_RUN_FILES)


def _find_latest_valid_run(runs_dir: Path) -> Path | None:
    if not runs_dir.exists():
        return None

    valid_runs = [candidate for candidate in runs_dir.iterdir() if _is_valid_discovery_run(candidate)]
    if not valid_runs:
        return None
    return sorted(valid_runs, key=lambda path: path.name, reverse=True)[0]


def _restore_latest_from_run(run_dir: Path, latest_dir: Path) -> None:
    latest_dir.mkdir(parents=True, exist_ok=True)
    for item in run_dir.iterdir():
        destination = latest_dir / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)


def resolve_makelaar_sources_master(
    input_path: Path | str | None = None,
    province: str | None = None,
    restore_latest: bool = True,
) -> Path:
    del province

    if input_path is not None:
        explicit_path = Path(input_path)
        if explicit_path.exists():
            return explicit_path
        raise FileNotFoundError(f"Input CSV not found: {explicit_path}")

    latest_path = DEFAULT_MAKELAAR_SOURCES_MASTER_PATH
    if latest_path.exists():
        return latest_path

    latest_dir = latest_path.parent
    runs_dir = latest_dir.parent / "runs"
    selected_run = _find_latest_valid_run(runs_dir)
    if selected_run is None:
        raise FileNotFoundError(
            "Discovery source master not found. Expected "
            f"{latest_path} or a valid run in {runs_dir}. Run scripts\\run_source_discovery.py first."
        )

    selected_master = selected_run / "makelaar_sources_master.csv"
    if restore_latest:
        _restore_latest_from_run(selected_run, latest_dir)
        _log(f"restored discovery latest from run {selected_run.name}")
        return latest_path
    return selected_master
