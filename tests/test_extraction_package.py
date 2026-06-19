from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))


def test_extraction_package_imports() -> None:
    import domek_wonen.extraction

    assert domek_wonen.extraction is not None
