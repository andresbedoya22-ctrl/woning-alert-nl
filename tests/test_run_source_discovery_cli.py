from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.run_source_discovery import parse_args


def test_cli_parse_args_supports_skip_overpass(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_source_discovery.py",
            "--province",
            "noord-brabant",
            "--mode",
            "full",
            "--max-sites",
            "1500",
            "--skip-overpass",
        ],
    )

    args = parse_args()

    assert args.province == "noord-brabant"
    assert args.mode == "full"
    assert args.max_sites == 1500
    assert args.skip_overpass is True
