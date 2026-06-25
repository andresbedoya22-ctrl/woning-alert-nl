from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))


def test_compliance_package_imports() -> None:
    import domek_wonen.compliance

    assert domek_wonen.compliance is not None
