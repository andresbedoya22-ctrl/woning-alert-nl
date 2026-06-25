from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.runtime_settings import load_runtime_settings


_ENV_KEYS = [
    "WNA_ENV",
    "WNA_USER_AGENT",
    "WNA_CONTACT_EMAIL",
    "WNA_REQUEST_TIMEOUT_SECONDS",
    "WNA_MAX_REQUESTS_PER_RUN",
    "WNA_MAX_REQUESTS_PER_DOMAIN",
    "WNA_MIN_REQUEST_INTERVAL_SECONDS",
    "WNA_RESPECT_ROBOTS_TX",
    "WNA_ENABLE_PLAYWRIGHT",
    "LLM_PROVIDER",
    "OPENAI_API_KEY",
    "LLM_MODEL",
    "ENABLE_LLM_EXTRACTION",
    "MAX_LLM_CALLS_PER_RUN",
    "MAX_LLM_TOKENS_PER_RUN",
    "WNA_STORAGE_BACKEND",
    "WNA_SQLITE_PATH",
]


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_defaults_are_safe_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    settings = load_runtime_settings(load_dotenv_file=False)
    assert settings.env == "local"
    assert settings.request_timeout_seconds == 20
    assert settings.max_requests_per_run == 100
    assert settings.max_requests_per_domain == 10
    assert settings.min_request_interval_seconds == 2
    assert settings.respect_robots_txt is True
    assert settings.enable_playwright is False
    assert settings.enable_llm_extraction is False
    assert settings.max_llm_calls_per_run == 0
    assert settings.max_llm_tokens_per_run == 0
    assert settings.llm_configured is False
    assert settings.llm_runtime_enabled is False


def test_llm_runtime_disabled_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("ENABLE_LLM_EXTRACTION", "true")
    monkeypatch.setenv("MAX_LLM_CALLS_PER_RUN", "1")
    settings = load_runtime_settings(load_dotenv_file=False)
    assert settings.llm_configured is False
    assert settings.llm_runtime_enabled is False


def test_llm_runtime_disabled_with_key_but_flag_false(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-test-key")
    monkeypatch.setenv("ENABLE_LLM_EXTRACTION", "false")
    monkeypatch.setenv("MAX_LLM_CALLS_PER_RUN", "1")
    settings = load_runtime_settings(load_dotenv_file=False)
    assert settings.llm_configured is True
    assert settings.llm_runtime_enabled is False


def test_llm_runtime_disabled_when_budget_is_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-test-key")
    monkeypatch.setenv("ENABLE_LLM_EXTRACTION", "true")
    monkeypatch.setenv("MAX_LLM_CALLS_PER_RUN", "0")
    settings = load_runtime_settings(load_dotenv_file=False)
    assert settings.llm_runtime_enabled is False


def test_llm_runtime_enabled_only_with_all_requirements(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-test-key")
    monkeypatch.setenv("ENABLE_LLM_EXTRACTION", "true")
    monkeypatch.setenv("MAX_LLM_CALLS_PER_RUN", "1")
    settings = load_runtime_settings(load_dotenv_file=False)
    assert settings.llm_configured is True
    assert settings.llm_runtime_enabled is True


@pytest.mark.parametrize(
    ("value", "expected"),
    [("true", True), ("1", True), ("yes", True), ("on", True), ("false", False), ("0", False), ("no", False), ("off", False), ("", False)],
)
def test_bool_parsing(monkeypatch: pytest.MonkeyPatch, value: str, expected: bool) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("ENABLE_LLM_EXTRACTION", value)
    settings = load_runtime_settings(load_dotenv_file=False)
    assert settings.enable_llm_extraction is expected


def test_invalid_integer_raises_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("MAX_LLM_CALLS_PER_RUN", "not-an-int")
    with pytest.raises(ValueError, match="MAX_LLM_CALLS_PER_RUN must be an integer"):
        load_runtime_settings(load_dotenv_file=False)


def test_timeout_must_be_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("WNA_REQUEST_TIMEOUT_SECONDS", "0")
    with pytest.raises(ValueError, match="WNA_REQUEST_TIMEOUT_SECONDS must be > 0"):
        load_runtime_settings(load_dotenv_file=False)


def test_negative_limits_raise_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("WNA_MAX_REQUESTS_PER_DOMAIN", "-1")
    with pytest.raises(ValueError, match="WNA_MAX_REQUESTS_PER_DOMAIN must be >= 0"):
        load_runtime_settings(load_dotenv_file=False)


def test_repr_masks_openai_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-test-key")
    settings = load_runtime_settings(load_dotenv_file=False)
    rendered = repr(settings)
    assert "dummy-test-key" not in rendered
    assert "***" in rendered
