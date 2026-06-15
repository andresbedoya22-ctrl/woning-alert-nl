from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from scripts.debug_kin_source import analyze_html, normalize_kin_url_to_https


def test_normalize_kin_url_to_https_upgrades_www_http() -> None:
    assert (
        normalize_kin_url_to_https("http://www.kinmakelaars.nl/aanbod/wonen/te-koop")
        == "https://www.kinmakelaars.nl/aanbod/wonen/te-koop"
    )


def test_analyze_html_detects_known_listing_markers() -> None:
    html = """
    <html>
      <head><title>KIN aanbod wonen te koop</title></head>
      <body>
        <div>248 resultaten</div>
        <div>Trouwlaan 285</div>
        <div>Roemerhof 16</div>
        <a href="/aanbod/wonen/trouwlaan-285-tilburg">Detail 1</a>
        <a href="/aanbod/wonen/roemerhof-16-tilburg">Detail 2</a>
        <a href="/aanbod/wonen/te-koop?page=2">Volgende</a>
      </body>
    </html>
    """

    result = analyze_html(html)

    assert result["title"] == "KIN aanbod wonen te koop"
    assert result["has_trouwlaan_285"] is True
    assert result["has_roemerhof_16"] is True
    assert result["has_results_count_hint"] is True
    assert result["detail_links_count"] >= 2
    assert result["pagination_links_count"] >= 1
