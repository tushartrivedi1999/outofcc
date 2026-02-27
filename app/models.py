from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field, HttpUrl

from app.domain import Plan


class SearchRequest(BaseModel):
    q: str = Field(min_length=1, max_length=512)
    num_results: int = Field(default=10, ge=1, le=50)
    language: str = Field(default="en")
    safe_search: bool = Field(default=True)
    freshness_days: int | None = Field(default=None, ge=1, le=365)


class SearchResult(BaseModel):
    title: str
    url: HttpUrl
    snippet: str
    engine: str
    score: float
    published_at: datetime | None = None


class SearchResponse(BaseModel):
    query: str
    took_ms: int
    cached: bool
    results: list[SearchResult]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApiKeyView(BaseModel):
    prefix: str
    plan: Plan
    created_at: datetime
