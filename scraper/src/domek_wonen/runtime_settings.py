from __future__ import annotations

import os
from dataclasses import dataclass


_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"", "0", "false", "no", "off"}


def _parse_bool(name: str, raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ValueError(f"{name} must be a boolean value")


def _parse_int(name: str, raw: str | None, default: int) -> int:
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    env: str = "local"
    user_agent: str = "WoningAlertNL/0.1 (+contact-email)"
    contact_email: str = ""
    request_timeout_seconds: int = 20
    max_requests_per_run: int = 100
    max_requests_per_domain: int = 10
    min_request_interval_seconds: int = 2
    respect_robots_txt: bool = True
    enable_playwright: bool = False
    llm_provider: str = "openai"
    openai_api_key: str = ""
    llm_model: str = ""
    enable_llm_extraction: bool = False
    max_llm_calls_per_run: int = 0
    max_llm_tokens_per_run: int = 0
    storage_backend: str = "sqlite"
    sqlite_path: str = "data/local/woningalert.sqlite"

    @property
    def llm_configured(self) -> bool:
        return self.llm_provider.strip().lower() == "openai" and bool(self.openai_api_key.strip())

    @property
    def llm_runtime_enabled(self) -> bool:
        return self.enable_llm_extraction and self.llm_configured and self.max_llm_calls_per_run > 0

    def __repr__(self) -> str:
        masked_key = "***" if self.openai_api_key else ""
        return (
            "RuntimeSettings("
            f"env={self.env!r}, "
            f"user_agent={self.user_agent!r}, "
            f"contact_email={self.contact_email!r}, "
            f"request_timeout_seconds={self.request_timeout_seconds!r}, "
            f"max_requests_per_run={self.max_requests_per_run!r}, "
            f"max_requests_per_domain={self.max_requests_per_domain!r}, "
            f"min_request_interval_seconds={self.min_request_interval_seconds!r}, "
            f"respect_robots_txt={self.respect_robots_txt!r}, "
            f"enable_playwright={self.enable_playwright!r}, "
            f"llm_provider={self.llm_provider!r}, "
            f"openai_api_key={masked_key!r}, "
            f"llm_model={self.llm_model!r}, "
            f"enable_llm_extraction={self.enable_llm_extraction!r}, "
            f"max_llm_calls_per_run={self.max_llm_calls_per_run!r}, "
            f"max_llm_tokens_per_run={self.max_llm_tokens_per_run!r}, "
            f"storage_backend={self.storage_backend!r}, "
            f"sqlite_path={self.sqlite_path!r})"
        )


def _validate(settings: RuntimeSettings) -> RuntimeSettings:
    if settings.max_requests_per_run < 0:
        raise ValueError("WNA_MAX_REQUESTS_PER_RUN must be >= 0")
    if settings.max_requests_per_domain < 0:
        raise ValueError("WNA_MAX_REQUESTS_PER_DOMAIN must be >= 0")
    if settings.max_llm_calls_per_run < 0:
        raise ValueError("MAX_LLM_CALLS_PER_RUN must be >= 0")
    if settings.max_llm_tokens_per_run < 0:
        raise ValueError("MAX_LLM_TOKENS_PER_RUN must be >= 0")
    if settings.request_timeout_seconds <= 0:
        raise ValueError("WNA_REQUEST_TIMEOUT_SECONDS must be > 0")
    if settings.min_request_interval_seconds < 0:
        raise ValueError("WNA_MIN_REQUEST_INTERVAL_SECONDS must be >= 0")
    return settings


def load_runtime_settings(load_dotenv_file: bool = True) -> RuntimeSettings:
    if load_dotenv_file:
        try:
            from dotenv import load_dotenv
        except ImportError:
            load_dotenv = None
        if load_dotenv is not None:
            load_dotenv(override=False)

    settings = RuntimeSettings(
        env=os.getenv("WNA_ENV", "local"),
        user_agent=os.getenv("WNA_USER_AGENT", "WoningAlertNL/0.1 (+contact-email)"),
        contact_email=os.getenv("WNA_CONTACT_EMAIL", ""),
        request_timeout_seconds=_parse_int("WNA_REQUEST_TIMEOUT_SECONDS", os.getenv("WNA_REQUEST_TIMEOUT_SECONDS"), 20),
        max_requests_per_run=_parse_int("WNA_MAX_REQUESTS_PER_RUN", os.getenv("WNA_MAX_REQUESTS_PER_RUN"), 100),
        max_requests_per_domain=_parse_int("WNA_MAX_REQUESTS_PER_DOMAIN", os.getenv("WNA_MAX_REQUESTS_PER_DOMAIN"), 10),
        min_request_interval_seconds=_parse_int(
            "WNA_MIN_REQUEST_INTERVAL_SECONDS", os.getenv("WNA_MIN_REQUEST_INTERVAL_SECONDS"), 2
        ),
        respect_robots_txt=_parse_bool("WNA_RESPECT_ROBOTS_TX", os.getenv("WNA_RESPECT_ROBOTS_TX"), True),
        enable_playwright=_parse_bool("WNA_ENABLE_PLAYWRIGHT", os.getenv("WNA_ENABLE_PLAYWRIGHT"), False),
        llm_provider=os.getenv("LLM_PROVIDER", "openai"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        llm_model=os.getenv("LLM_MODEL", ""),
        enable_llm_extraction=_parse_bool("ENABLE_LLM_EXTRACTION", os.getenv("ENABLE_LLM_EXTRACTION"), False),
        max_llm_calls_per_run=_parse_int("MAX_LLM_CALLS_PER_RUN", os.getenv("MAX_LLM_CALLS_PER_RUN"), 0),
        max_llm_tokens_per_run=_parse_int("MAX_LLM_TOKENS_PER_RUN", os.getenv("MAX_LLM_TOKENS_PER_RUN"), 0),
        storage_backend=os.getenv("WNA_STORAGE_BACKEND", "sqlite"),
        sqlite_path=os.getenv("WNA_SQLITE_PATH", "data/local/woningalert.sqlite"),
    )
    return _validate(settings)
