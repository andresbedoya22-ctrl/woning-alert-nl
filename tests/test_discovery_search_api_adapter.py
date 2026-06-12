from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.discovery.models import GeneratedQuery
from domek_wonen.discovery.search_api_adapter import SearchApiAdapter


def test_search_api_adapter_disables_without_credentials() -> None:
    adapter = SearchApiAdapter(api_key="", search_engine_id="")

    response = adapter.search([GeneratedQuery(gemeente="Breda", query="makelaar Breda", template="x")])

    assert response.status == "disabled_missing_credentials"
    assert response.results == []
