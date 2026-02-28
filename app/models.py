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


class AgentContextRequest(BaseModel):
    query: str = Field(min_length=1, max_length=512)
    top_k: int = Field(default=8, ge=1, le=20)
    include_domains: list[str] = Field(default_factory=list)
    exclude_domains: list[str] = Field(default_factory=list)


class AgentContextChunk(BaseModel):
    title: str
    url: HttpUrl
    snippet: str
    score: float
    source_engine: str


class AgentContextResponse(BaseModel):
    query: str
    answer_brief: str
    citations: list[str]
    context_chunks: list[AgentContextChunk]
    freshness_hint: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DatasetCreateRequest(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    query: str = Field(min_length=1, max_length=512)
    source: str = Field(default="open-search", pattern="^(open-search|commoncrawl)$")
    rows: int = Field(default=100, ge=10, le=5000)
