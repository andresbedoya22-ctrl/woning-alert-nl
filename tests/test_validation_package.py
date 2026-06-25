from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))


def test_validation_package_imports() -> None:
    import domek_wonen.validation

    assert domek_wonen.validation is not None
