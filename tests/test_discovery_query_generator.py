from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.discovery.query_generator import generate_queries_for_gemeente, generate_queries_from_reference


def test_query_generation_includes_veldhoven_and_valkenswaard() -> None:
    queries = generate_queries_from_reference()

    query_strings = {query.query for query in queries}
    assert "makelaar koopwoningen Veldhoven" in query_strings
    assert "makelaar koopwoningen Valkenswaard" in query_strings


def test_query_generation_respects_max_queries() -> None:
    queries = generate_queries_for_gemeente("Veldhoven", max_queries=3)

    assert len(queries) == 3
    assert queries[0].query == "makelaar koopwoningen Veldhoven"
