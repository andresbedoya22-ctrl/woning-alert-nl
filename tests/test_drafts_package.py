from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))


def test_drafts_package_imports() -> None:
    import domek_wonen.drafts

    assert domek_wonen.drafts is not None
