from __future__ import annotations

import os
from dataclasses import dataclass, field

from .models import GeneratedQuery


@dataclass(slots=True)
class SearchResult:
    title: str
    snippet: str
    url: str
    root_domain: str
    source_query: str


@dataclass(slots=True)
class SearchApiResponse:
    status: str
    results: list[SearchResult] = field(default_factory=list)


class SearchApiAdapter:
    def __init__(
        self,
        api_key: str | None = None,
        search_engine_id: str | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("GOOGLE_CUSTOM_SEARCH_API_KEY", "")
        self.search_engine_id = (
            search_engine_id
            if search_engine_id is not None
            else os.getenv("GOOGLE_CUSTOM_SEARCH_ENGINE_ID", "")
        )

    def status(self) -> str:
        if not self.api_key or not self.search_engine_id:
            return "disabled_missing_credentials"
        return "configured_future_google_custom_search"

    def search(self, queries: list[GeneratedQuery], max_sites: int | None = None) -> SearchApiResponse:
        _ = queries
        _ = max_sites
        return SearchApiResponse(status=self.status(), results=[])
