from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))


def test_changes_package_imports() -> None:
    import domek_wonen.changes

    assert domek_wonen.changes is not None
