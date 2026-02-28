# Open Search Platform (Searx-first)

A unified production-oriented platform with:
- Search API (Google Search API alternative)
- Open Search Console (Google Search Console-style module)
- Agent Context Studio (Tavily-style module for LLM/agent grounding)
- Dataset creation pipeline (Open Search/CommonCrawl-style sources)
- Internal Engine Blog (project updates and release notes)

> **Core principle:** this project is **Searx-first**. Retrieval originates from Searx, and all product modules build on top of that data backbone.

## Documentation

Comprehensive docs are in `docs/`:
- `docs/README.md` - docs index
- `docs/architecture.md`
- `docs/apis.md`
- `docs/search-console.md`
- `docs/agent-context.md`
- `docs/security.md`
- `docs/operations.md`
- `INTEGRATION_GUIDE.md` - end-to-end integration playbook

## Product modules

### 1) Search API
- Endpoint: `POST /v1/search`
- API-key auth + plan-based rate limits
- cache + reranking + Searx connector

### 2) Open Search Console
- Route: `/console`
- property onboarding and verification
- analytics and issue diagnostics

### 3) Agent Context Studio (Tavily alternative)
- Route: `/agent`
- Endpoint: `POST /v1/agent/context`
- structured context output: answer brief, citations, chunks, freshness hint

### 4) Dataset creation
- UI in `/agent`
- API: `POST /v1/agent/datasets/create`
- sources: `open-search`, `commoncrawl`

### 5) Internal Engine Blog
- Routes: `/blog`, `/blog/new`, `/blog/{slug}`
- publish product updates and architecture notes

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
set -a && source .env && set +a
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Default admin login: `admin/admin`

## API examples

### Search
```bash
curl -X POST http://localhost:8000/v1/search \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"q":"latest llm retrieval methods", "num_results": 5}'
```

### Agent context
```bash
curl -X POST http://localhost:8000/v1/agent/context \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"query":"latest llm eval benchmarks", "top_k": 8}'
```

### Dataset creation
```bash
curl -X POST http://localhost:8000/v1/agent/datasets/create \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"name":"llm-benchmark-corpus", "query":"llm benchmarks", "source":"open-search", "rows":120}'
```

## Stress, monkey and load-balance tests

```bash
python scripts/load_test.py --base-url http://localhost:8000 --api-key <YOUR_API_KEY> --concurrency 50 --requests 2000
python scripts/monkey_test.py
python scripts/load_balance_test.py
```

## Production readiness note

The current project is a strong foundation. For full production readiness:
- move SQLite to Postgres
- move in-memory limiter/cache to Redis
- add real DNS/file probe verification workers
- add observability, SLOs, RBAC, billing, and abuse controls

## GitHub push

```bash
git remote add origin https://github.com/<your-org-or-user>/<repo>.git
git push -u origin <your-branch>
```


## Code optimization highlights

- Shared helpers removed duplicate rendering and dataset-row generation logic.
- SQLite is configured with WAL + foreign key enforcement for safer concurrent usage.
- Bulk inserts now use batched writes for better throughput under load.
