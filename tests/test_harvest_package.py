from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))


def test_harvest_package_imports() -> None:
    import domek_wonen.harvest

    assert domek_wonen.harvest is not None
