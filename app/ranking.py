from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime, timezone

from app.models import SearchResult


_TOKENIZER = re.compile(r"[a-zA-Z0-9]+")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKENIZER.findall(text)]


def _text_relevance(query: str, title: str, snippet: str) -> float:
    q = Counter(_tokenize(query))
    d = Counter(_tokenize(f"{title} {snippet}"))
    if not q or not d:
        return 0.0

    dot = sum(q[token] * d[token] for token in q)
    q_norm = math.sqrt(sum(v * v for v in q.values()))
    d_norm = math.sqrt(sum(v * v for v in d.values()))
    if q_norm == 0 or d_norm == 0:
        return 0.0
    return dot / (q_norm * d_norm)


def _freshness_boost(published_at: datetime | None) -> float:
    if not published_at:
        return 0.0
    age_days = max((datetime.now(timezone.utc) - published_at).days, 0)
    return max(0.0, 1.0 - (age_days / 365))


def rerank(query: str, results: list[SearchResult]) -> list[SearchResult]:
    rescored = []
    for item in results:
        relevance = _text_relevance(query=query, title=item.title, snippet=item.snippet)
        freshness = _freshness_boost(item.published_at)
        item.score = round(0.85 * relevance + 0.15 * freshness, 5)
        rescored.append(item)
    return sorted(rescored, key=lambda r: r.score, reverse=True)
