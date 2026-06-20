from __future__ import annotations

import ast
import csv
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.discovery.census import DiscoveryStrategy, DomainClassification
from domek_wonen.runtime_settings import RuntimeSettings
from scripts import run_discovery_census


@pytest.fixture(autouse=True)
def runtime_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_load_runtime_settings(load_dotenv_file: bool = True) -> RuntimeSettings:
        return RuntimeSettings(
            min_request_interval_seconds=2,
            request_timeout_seconds=20,
        )

    monkeypatch.setattr("scripts.run_discovery_census.load_runtime_settings", fake_load_runtime_settings)


def write_registry(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    registry_path = tmp_path / "makelaar_sources_master.csv"
    with registry_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["root_domain", "is_active"])
        writer.writeheader()
        writer.writerows(rows)
    return registry_path


def make_classification(
    domain: str,
    strategy: DiscoveryStrategy,
    *,
    cms: str = "unknown",
    blocker_reason: str | None = None,
    needs_js: bool = False,
    crawl_delay: float = 0.0,
) -> DomainClassification:
    return DomainClassification(
        domain=domain,
        robots_status="allow",
        robots_crawl_delay=crawl_delay,
        discovery_strategy=strategy,
        cms_fingerprint_guess=cms,
        sitemap_found=False,
        sitemap_has_listing_urls=False,
        wp_json_listings_found=False,
        listing_url_pattern=None,
        card_fields_extractable=[],
        needs_js=needs_js,
        requests_used=1,
        recommended_action="manual_review",
        blocker_reason=blocker_reason,
    )


def test_registry_loading(tmp_path: Path) -> None:
    registry_path = write_registry(
        tmp_path,
        [
            {"root_domain": "alpha.nl", "is_active": "true"},
            {"root_domain": "", "is_active": "true"},
            {"root_domain": "beta.nl", "is_active": "false"},
            {"root_domain": "gamma.nl", "is_active": "1"},
        ],
    )

    domains = run_discovery_census.load_registry_domains(registry_path, "root_domain")

    assert domains == ["alpha.nl", "gamma.nl"]


def test_sample_reproducible() -> None:
    domains = [f"domain-{index}.nl" for index in range(10)]

    sample_one, used_all_one = run_discovery_census.sample_domains(domains, sample_size=4, seed=42)
    sample_two, used_all_two = run_discovery_census.sample_domains(domains, sample_size=4, seed=42)
    sample_three, _ = run_discovery_census.sample_domains(domains, sample_size=4, seed=7)

    assert used_all_one is False
    assert used_all_two is False
    assert sample_one == sample_two
    assert sample_one != sample_three


def test_sample_smaller_than_registry() -> None:
    domains = ["alpha.nl", "beta.nl"]

    sampled, used_all_domains = run_discovery_census.sample_domains(domains, sample_size=30, seed=42)

    assert sampled == domains
    assert used_all_domains is True


def test_dedupe_domains(tmp_path: Path) -> None:
    registry_path = write_registry(
        tmp_path,
        [
            {"root_domain": "alpha.nl", "is_active": "true"},
            {"root_domain": "alpha.nl", "is_active": "true"},
            {"root_domain": "beta.nl", "is_active": "true"},
        ],
    )

    domains = run_discovery_census.load_registry_domains(registry_path, "root_domain")

    assert domains == ["alpha.nl", "beta.nl"]


def test_classify_called_per_domain() -> None:
    calls: list[str] = []

    def fake_classify(domain: str) -> DomainClassification:
        calls.append(domain)
        return make_classification(domain, DiscoveryStrategy.no_signal)

    results = run_discovery_census.classify_domains(
        ["alpha.nl", "beta.nl"],
        classify=fake_classify,
        delay_seconds=0,
        sleep=lambda _seconds: None,
    )

    assert [item.domain for item in results] == ["alpha.nl", "beta.nl"]
    assert calls == ["alpha.nl", "beta.nl"]


def test_domain_failure_does_not_stop_run() -> None:
    def fake_classify(domain: str) -> DomainClassification:
        if domain == "beta.nl":
            raise RuntimeError("boom")
        return make_classification(domain, DiscoveryStrategy.listing_html)

    results = run_discovery_census.classify_domains(
        ["alpha.nl", "beta.nl", "gamma.nl"],
        classify=fake_classify,
        delay_seconds=0,
        sleep=lambda _seconds: None,
    )

    assert [item.domain for item in results] == ["alpha.nl", "beta.nl", "gamma.nl"]
    assert results[1].discovery_strategy is DiscoveryStrategy.blocked
    assert results[1].blocker_reason == "exception:RuntimeError"
    assert results[2].discovery_strategy is DiscoveryStrategy.listing_html


def test_distribution_aggregation() -> None:
    summary = run_discovery_census.compute_summary(
        [
            make_classification("alpha.nl", DiscoveryStrategy.listing_html, cms="wordpress"),
            make_classification("beta.nl", DiscoveryStrategy.wp_json, cms="wordpress"),
            make_classification("gamma.nl", DiscoveryStrategy.blocked, cms="unknown", blocker_reason="http_403"),
            make_classification("delta.nl", DiscoveryStrategy.listing_js, cms="realworks", needs_js=True),
        ]
    )

    assert summary["strategy_counts"]["listing_html"] == 1
    assert summary["strategy_counts"]["wp_json"] == 1
    assert summary["strategy_counts"]["blocked"] == 1
    assert summary["strategy_counts"]["listing_js"] == 1
    assert summary["cms_counts"]["wordpress"] == 2
    assert summary["blocked_percent"] == 25.0
    assert summary["needs_js_percent"] == 25.0


def test_verdict_green() -> None:
    summary = run_discovery_census.compute_summary(
        [
            make_classification("a.nl", DiscoveryStrategy.listing_html),
            make_classification("b.nl", DiscoveryStrategy.wp_json),
            make_classification("c.nl", DiscoveryStrategy.sitemap_with_listings),
            make_classification("d.nl", DiscoveryStrategy.blocked, blocker_reason="http_403"),
        ]
    )

    assert summary["discoverable_percent"] == 75.0
    assert summary["verdict"] == "VERDE: construir Bloques 2-7"


def test_verdict_yellow() -> None:
    summary = run_discovery_census.compute_summary(
        [
            make_classification("a.nl", DiscoveryStrategy.listing_html),
            make_classification("b.nl", DiscoveryStrategy.wp_json),
            make_classification("c.nl", DiscoveryStrategy.blocked, blocker_reason="http_403"),
            make_classification("d.nl", DiscoveryStrategy.no_signal),
        ]
    )

    assert summary["discoverable_percent"] == 50.0
    assert summary["verdict"] == "AMARILLO: construir verdes + decidir JS"


def test_verdict_red() -> None:
    summary = run_discovery_census.compute_summary(
        [
            make_classification("b.nl", DiscoveryStrategy.blocked, blocker_reason="http_403"),
            make_classification("c.nl", DiscoveryStrategy.listing_js, needs_js=True),
            make_classification("d.nl", DiscoveryStrategy.no_signal),
        ]
    )

    assert summary["discoverable_percent"] == 0.0
    assert summary["verdict"] == "ROJO: track comercial (Realworks/Kolibri)"


def test_dry_run_no_requests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    registry_path = write_registry(
        tmp_path,
        [
            {"root_domain": "alpha.nl", "is_active": "true"},
            {"root_domain": "beta.nl", "is_active": "true"},
        ],
    )

    monkeypatch.setattr("scripts.run_discovery_census.resolve_registry_path", lambda _registry: registry_path)
    monkeypatch.setattr(
        "scripts.run_discovery_census.classify_domains",
        lambda *args, **kwargs: pytest.fail("dry-run should not classify domains"),
    )

    exit_code = run_discovery_census.main(["--registry", str(registry_path), "--dry-run", "--sample", "30"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Discovery census dry-run" in output
    assert "registry=" in output
    assert "alpha.nl" in output
    assert "beta.nl" in output


def test_outputs_written(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    report_text = "# Discovery Census Report\n"
    classifications = [
        make_classification("alpha.nl", DiscoveryStrategy.listing_html),
        make_classification("beta.nl", DiscoveryStrategy.blocked, blocker_reason="http_403"),
    ]

    inventory_path, report_path = run_discovery_census.write_outputs(output_dir, classifications, report_text)

    assert inventory_path.exists()
    assert report_path.exists()
    with inventory_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    assert rows[0]["domain"] == "alpha.nl"
    assert report_path.read_text(encoding="utf-8") == report_text


def test_no_legacy_imports() -> None:
    source_path = Path(__file__).resolve().parents[1] / "scripts" / "run_discovery_census.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    banned_fragments = (
        "portals",
        "properties",
        "adapters",
        "legacy",
    )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        for name in names:
            assert not any(fragment in name for fragment in banned_fragments)


def test_render_report_includes_uncovered_reason() -> None:
    summary = run_discovery_census.compute_summary(
        [
            make_classification("alpha.nl", DiscoveryStrategy.listing_html, cms="wordpress"),
            make_classification("beta.nl", DiscoveryStrategy.blocked, blocker_reason="http_429"),
        ]
    )

    report = run_discovery_census.render_report(
        run_id="20260620T120000Z",
        generated_at="2026-06-20T12:00:00+00:00",
        registry_path=Path("registry.csv"),
        sample_size=30,
        seed=42,
        used_all_domains=True,
        domains=["alpha.nl", "beta.nl"],
        summary=summary,
    )

    assert "## Distribution by discovery_strategy" in report
    assert "- beta.nl: blocked (http_429)" in report


def test_main_writes_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry_path = write_registry(
        tmp_path,
        [
            {"root_domain": "alpha.nl", "is_active": "true"},
            {"root_domain": "beta.nl", "is_active": "true"},
        ],
    )
    output_dir = tmp_path / "report"

    monkeypatch.setattr("scripts.run_discovery_census.resolve_registry_path", lambda _registry: registry_path)
    monkeypatch.setattr(
        "scripts.run_discovery_census.classify_domains",
        lambda domains, **_kwargs: [
            make_classification(domains[0], DiscoveryStrategy.listing_html, cms="wordpress"),
            make_classification(domains[1], DiscoveryStrategy.blocked, blocker_reason="http_403"),
        ],
    )

    exit_code = run_discovery_census.main(
        ["--registry", str(registry_path), "--output-dir", str(output_dir), "--sample", "2", "--seed", "42"]
    )

    assert exit_code == 0
    assert (output_dir / "census_inventory.csv").exists()
    assert (output_dir / "census_report.md").exists()


def test_timeout_seconds_env_uses_integer_string(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str | None] = []

    def fake_classify(domain: str) -> DomainClassification:
        captured.append(__import__("os").environ.get("WNA_REQUEST_TIMEOUT_SECONDS"))
        return make_classification(domain, DiscoveryStrategy.no_signal)

    monkeypatch.delenv("WNA_REQUEST_TIMEOUT_SECONDS", raising=False)

    run_discovery_census.classify_domains(
        ["alpha.nl"],
        classify=fake_classify,
        delay_seconds=0,
        timeout_seconds=20.0,
        sleep=lambda _seconds: None,
    )

    assert captured == ["20"]
