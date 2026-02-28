from __future__ import annotations

from dataclasses import dataclass

from app.models import AgentContextChunk, AgentContextRequest, AgentContextResponse, SearchRequest, SearchResponse
from app.service import SearchService


@dataclass
class AgentContextService:
    search_service: SearchService

    async def build_context(self, request: AgentContextRequest) -> AgentContextResponse:
        search_response: SearchResponse = await self.search_service.search(
            SearchRequest(q=request.query, num_results=max(request.top_k, 10), safe_search=True)
        )
        chunks: list[AgentContextChunk] = []
        for row in search_response.results:
            host = str(row.url)
            if request.include_domains and not any(domain in host for domain in request.include_domains):
                continue
            if request.exclude_domains and any(domain in host for domain in request.exclude_domains):
                continue
            chunks.append(
                AgentContextChunk(
                    title=row.title,
                    url=row.url,
                    snippet=row.snippet,
                    score=row.score,
                    source_engine=row.engine,
                )
            )
            if len(chunks) >= request.top_k:
                break

        citations = [str(item.url) for item in chunks[:5]]
        if chunks:
            first = chunks[0]
            brief = f"Top context from '{first.title}' plus {max(len(chunks)-1, 0)} supporting sources."
        else:
            brief = "No reliable context found for this query."

        freshness_hint = "fresh" if search_response.took_ms < 1500 else "stale-risk"
        return AgentContextResponse(
            query=request.query,
            answer_brief=brief,
            citations=citations,
            context_chunks=chunks,
            freshness_hint=freshness_hint,
        )
