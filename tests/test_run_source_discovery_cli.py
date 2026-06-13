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


def test_cli_parse_args_supports_live_aanbod_zero_limit(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_source_discovery.py",
            "--province",
            "noord-brabant",
            "--live-aanbod",
            "--max-live-sites",
            "0",
        ],
    )

    args = parse_args()

    assert args.live_aanbod is True
    assert args.max_live_sites == 0


def test_cli_parse_args_supports_audit_aanbod(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_source_discovery.py",
            "--province",
            "noord-brabant",
            "--audit-aanbod",
            "--max-audited-sites",
            "20",
            "--audit-confidence-threshold",
            "90",
        ],
    )

    args = parse_args()

    assert args.audit_aanbod is True
    assert args.max_audited_sites == 20
    assert args.audit_confidence_threshold == 90
