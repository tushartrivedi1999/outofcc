from __future__ import annotations

import hashlib
import json
import time

from app.cache import TTLCache
from app.clients.searx_client import SearxClient
from app.config import SETTINGS
from app.models import SearchRequest, SearchResponse
from app.ranking import rerank


class SearchService:
    def __init__(self, searx_client: SearxClient, cache: TTLCache[SearchResponse]) -> None:
        self._searx_client = searx_client
        self._cache = cache

    @staticmethod
    def _cache_key(request: SearchRequest) -> str:
        serialized = json.dumps(request.model_dump(), sort_keys=True)
        return hashlib.sha1(serialized.encode("utf-8")).hexdigest()

    async def search(self, request: SearchRequest) -> SearchResponse:
        start = time.perf_counter()
        key = self._cache_key(request)

        cached = self._cache.get(key)
        if cached:
            return cached.model_copy(update={"cached": True})

        try:
            raw_results = await self._searx_client.search(
                query=request.q,
                language=request.language,
                safe_search=request.safe_search,
                num_results=request.num_results,
            )
        except Exception:
            took_ms = int((time.perf_counter() - start) * 1000)
            return SearchResponse(query=request.q, took_ms=took_ms, cached=False, results=[])

        reranked = rerank(query=request.q, results=raw_results)[: request.num_results]
        took_ms = int((time.perf_counter() - start) * 1000)

        response = SearchResponse(
            query=request.q,
            took_ms=took_ms,
            cached=False,
            results=reranked,
        )
        self._cache.set(key, response, ttl_s=SETTINGS.cache_ttl_s)
        return response
