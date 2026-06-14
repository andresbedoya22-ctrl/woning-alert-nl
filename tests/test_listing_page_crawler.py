from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.properties.listing_page_crawler import ListingPageCrawler


def test_listing_page_crawler_close_ignores_browser_close_failure() -> None:
    crawler = ListingPageCrawler()

    class FakeBrowser:
        def close(self) -> None:
            raise RuntimeError("browser close failed")

    class FakePlaywright:
        def stop(self) -> None:
            return None

    crawler._browser = FakeBrowser()
    crawler._playwright = FakePlaywright()

    crawler.close()

    assert crawler._browser is None
    assert crawler._playwright is None
