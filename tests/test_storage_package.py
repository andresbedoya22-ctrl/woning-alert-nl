from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))


def test_storage_package_imports() -> None:
    import domek_wonen.storage

    assert domek_wonen.storage is not None
