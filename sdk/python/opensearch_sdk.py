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

    def search(self, query: str, num_results: int = 10, language: str = "en", safe_search: bool = True) -> dict[str, Any]:
        payload = {
            "q": query,
            "num_results": num_results,
            "language": language,
            "safe_search": safe_search,
        }
        req = request.Request(
            url=f"{self.base_url.rstrip('/')}/v1/search",
            method="POST",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        with request.urlopen(req, timeout=self.timeout_s) as response:
            return json.loads(response.read().decode("utf-8"))
