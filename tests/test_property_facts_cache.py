from __future__ import annotations

import ast
import json
from datetime import UTC, datetime
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.facts import PropertyFactsCache, build_property_fact_value, build_property_facts_record


FACTS_DIR = BASE_DIR / "scraper" / "src" / "domek_wonen" / "facts"
PILOTS_DIR = BASE_DIR / "scraper" / "src" / "domek_wonen" / "pilots"


def _record(url: str = "https://kinmakelaars.nl/a", fetched_at: str = "2026-06-27T00:00:00Z", schema_version: str = "property_facts_v1"):
    return build_property_facts_record(
        schema_version=schema_version,
        source_id="kinmakelaars.nl__breda",
        source_domain="kinmakelaars.nl",
        canonical_url=url,
        fetched_at=fetched_at,
        expires_at="2026-07-11T00:00:00Z",
        facts=(
            build_property_fact_value(
                field="asking_price",
                value="425000",
                normalized_value=425000,
                unit="EUR",
                source="metadata",
                confidence=1.0,
                status="usable",
                evidence_preview="425000",
            ),
        ),
    )


def test_cache_upsert_get_roundtrip(tmp_path: Path) -> None:
    cache = PropertyFactsCache(tmp_path / "facts.jsonl")
    record = _record()

    cache.upsert(record)

    assert cache.get(record.canonical_url, record.source_domain) == record


def test_upsert_many_dedupes_by_key(tmp_path: Path) -> None:
    cache = PropertyFactsCache(tmp_path / "facts.jsonl")

    cache.upsert_many((_record(fetched_at="2026-06-26T00:00:00Z"), _record(fetched_at="2026-06-27T00:00:00Z")))

    assert len(cache.load_all()) == 1
    assert cache.load_all()[0].fetched_at == "2026-06-27T00:00:00Z"


def test_newer_replaces_older_and_older_does_not_replace_newer(tmp_path: Path) -> None:
    cache = PropertyFactsCache(tmp_path / "facts.jsonl")
    newer = _record(fetched_at="2026-06-27T00:00:00Z")
    older = _record(fetched_at="2026-06-26T00:00:00Z")

    cache.upsert(older)
    cache.upsert(newer)
    cache.upsert(older)

    assert cache.get(newer.canonical_url, newer.source_domain) == newer


def test_is_stale_after_expires_at(tmp_path: Path) -> None:
    cache = PropertyFactsCache(tmp_path / "facts.jsonl")
    record = _record()

    assert cache.is_stale(record, datetime(2026, 7, 12, tzinfo=UTC)) is True


def test_schema_version_mismatch_behaves_as_miss_and_stale(tmp_path: Path) -> None:
    cache = PropertyFactsCache(tmp_path / "facts.jsonl")
    record = _record(schema_version="property_facts_v0")
    cache.upsert(record)

    assert cache.get(record.canonical_url, record.source_domain) is None
    assert cache.is_stale(record, datetime(2026, 6, 27, tzinfo=UTC)) is True


def test_atomic_write_leaves_valid_jsonl(tmp_path: Path) -> None:
    cache = PropertyFactsCache(tmp_path / "facts.jsonl")

    cache.upsert_many((_record(url="https://kinmakelaars.nl/a"), _record(url="https://kinmakelaars.nl/b")))

    for line in cache.path.read_text(encoding="utf-8").splitlines():
        assert json.loads(line)["schema_version"] == "property_facts_v1"


def test_load_all_skips_malformed_lines(tmp_path: Path) -> None:
    cache = PropertyFactsCache(tmp_path / "facts.jsonl")
    cache.upsert(_record())
    cache.path.write_text(cache.path.read_text(encoding="utf-8") + "{bad json}\n", encoding="utf-8")

    assert len(cache.load_all()) == 1


def test_cache_does_not_write_html_or_raw_json(tmp_path: Path) -> None:
    cache = PropertyFactsCache(tmp_path / "facts.jsonl")
    cache.upsert(_record())

    content = cache.path.read_text(encoding="utf-8").casefold()
    assert "<html" not in content
    assert "window.__" not in content


def test_cache_does_not_touch_data_raw(tmp_path: Path) -> None:
    cache_path = tmp_path / "nested" / "facts.jsonl"
    cache = PropertyFactsCache(cache_path)
    cache.upsert(_record())

    assert cache_path.exists()
    assert not (BASE_DIR / "data" / "raw" / "facts.jsonl").exists()


def test_new_facts_modules_have_no_disallowed_imports() -> None:
    disallowed = {"requests", "httpx", "playwright", "selenium"}
    for module_path in FACTS_DIR.glob("*.py"):
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        imported_modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
        assert disallowed.isdisjoint({module.split(".")[0] for module in imported_modules})


def test_no_new_probe_or_extractor_writes_outside_cache() -> None:
    write_methods = {"write_text", "write_bytes"}
    for module_path in PILOTS_DIR.glob("ogonline_detail*_*.py"):
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in write_methods
