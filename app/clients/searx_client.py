from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.models import SearchResult


class SearxClient:
    def __init__(self, base_url: str, timeout_s: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_s

    async def search(
        self,
        query: str,
        language: str,
        safe_search: bool,
        num_results: int,
    ) -> list[SearchResult]:
        params = {
            "q": query,
            "format": "json",
            "language": language,
            "safesearch": 1 if safe_search else 0,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(f"{self._base_url}/search", params=params)
            response.raise_for_status()
            payload = response.json()

        return self._to_results(payload, num_results)

    def _to_results(self, payload: dict[str, Any], limit: int) -> list[SearchResult]:
        results: list[SearchResult] = []
        for row in payload.get("results", [])[:limit * 2]:
            published = None
            if row.get("publishedDate"):
                try:
                    published = datetime.fromisoformat(row["publishedDate"].replace("Z", "+00:00"))
                except ValueError:
                    published = None

            try:
                results.append(
                    SearchResult(
                        title=row.get("title", ""),
                        url=row.get("url", "https://example.invalid"),
                        snippet=row.get("content", ""),
                        engine=",".join(row.get("engines", [])) or "searx",
                        score=0.0,
                        published_at=published,
                    )
                )
            except Exception:
                continue
        return results[:limit]
