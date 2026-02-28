from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib import request


@dataclass
class OpenSearchSDK:
    base_url: str
    api_key: str
    timeout_s: float = 10.0

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        req = request.Request(
            url=f"{self.base_url.rstrip('/')}{path}",
            method="POST",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        with request.urlopen(req, timeout=self.timeout_s) as response:
            return json.loads(response.read().decode("utf-8"))

    def search(self, query: str, num_results: int = 10, language: str = "en", safe_search: bool = True) -> dict[str, Any]:
        return self._post(
            "/v1/search",
            {"q": query, "num_results": num_results, "language": language, "safe_search": safe_search},
        )

    def agent_context(self, query: str, top_k: int = 8) -> dict[str, Any]:
        return self._post("/v1/agent/context", {"query": query, "top_k": top_k})

    def create_dataset(self, name: str, query: str, source: str = "open-search", rows: int = 100) -> dict[str, Any]:
        return self._post(
            "/v1/agent/datasets/create",
            {"name": name, "query": query, "source": source, "rows": rows},
        )
