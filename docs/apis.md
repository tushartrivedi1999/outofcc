# API Reference

## Authentication

Use API key as bearer token:

`Authorization: Bearer <API_KEY>`

---

## POST /v1/search

### Request

```json
{
  "q": "latest llm eval benchmark",
  "num_results": 10,
  "language": "en",
  "safe_search": true
}
```

### Response

Returns normalized search response with ranked results and metadata.

---

## POST /v1/agent/context

Tavily-style structured context for AI agents.

### Request

```json
{
  "query": "latest rag security patterns",
  "top_k": 8,
  "include_domains": [],
  "exclude_domains": []
}
```

### Response

```json
{
  "query": "...",
  "answer_brief": "...",
  "citations": ["https://..."],
  "context_chunks": [
    {
      "title": "...",
      "url": "https://...",
      "snippet": "...",
      "score": 0.87,
      "source_engine": "..."
    }
  ],
  "freshness_hint": "fresh"
}
```

---

## POST /v1/agent/datasets/create

Creates dataset metadata and rows.

### Request

```json
{
  "name": "rag-corpus-v1",
  "query": "retrieval augmented generation",
  "source": "open-search",
  "rows": 100
}
```

### Response

```json
{
  "dataset_id": 1,
  "rows": 100,
  "source": "open-search",
  "status": "ready"
}
```
