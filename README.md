# Open Search Platform (API + Console + Agent Context)

A single production-oriented project that combines:
- **Search API platform** (Google Search API alternative)
- **Open Search Console** (Google Search Console-style property/verification/analytics)
- **Agent Context Studio** (Tavily-style context API for AI agents, LLMs, SLMs)
- **Dataset creation pipeline** (from Open Search or CommonCrawl-style source)

## Why this matters

This stack is designed for grounded AI systems:
- fresh and structured context retrieval
- citations and context chunks for trustable outputs
- property insights and issue diagnostics for website owners
- API + dashboard + console in one deployable product

## Platform modules

- `app/main.py` - all routes for auth, dashboard, search API, console, agent context, dataset creation
- `app/service.py` - retrieval + rerank + cache pipeline
- `app/agent_context.py` - Tavily-style context construction
- `app/console.py` - verification payloads and chart generators
- `app/user_store.py` - persistence (users, keys, sites, metrics, issues, usage, datasets)
- `sdk/python/opensearch_sdk.py` - Python SDK for search API
- `scripts/load_test.py` - stress/load testing with distortion detection
- `INTEGRATION_GUIDE.md` - step-by-step integration document

## Features

### Search API
- API key auth with plans (`free`, `pro`, `enterprise`)
- rate limiting, cache, reranking
- Searx-backed retrieval

### Open Search Console
- add property by domain/URL prefix
- verify ownership by DNS or URL-prefix method
- view performance analytics and issues

### Agent Context Studio (Tavily alternative)
- dashboard button: **Agent Context Studio** (`/agent`)
- structured context generation for AI agents
- outputs answer brief + citations + context chunks + freshness hint
- API endpoint: `POST /v1/agent/context`

### Dataset creation
- UI and API-driven dataset creation
- sources: `open-search`, `commoncrawl`
- API endpoint: `POST /v1/agent/datasets/create`

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
set -a && source .env && set +a
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Default login: `admin/admin`

## API examples

### Search
```bash
curl -X POST http://localhost:8000/v1/search \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"q":"best retrieval augmented generation patterns", "num_results": 5}'
```

### Agent context (Tavily-style)
```bash
curl -X POST http://localhost:8000/v1/agent/context \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"query":"latest llm security benchmarks", "top_k": 8}'
```

### Dataset creation
```bash
curl -X POST http://localhost:8000/v1/agent/datasets/create \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"name":"llm-security-corpus", "query":"llm security", "source":"open-search", "rows":100}'
```

## Stress testing

```bash
python scripts/load_test.py --base-url http://localhost:8000 --api-key <YOUR_API_KEY> --concurrency 50 --requests 2000
```

## Integration docs

See **`INTEGRATION_GUIDE.md`** for step-by-step integration into your current product.

## Push to GitHub

```bash
git remote add origin https://github.com/<your-org-or-user>/<repo>.git
git push -u origin <your-branch>
```
