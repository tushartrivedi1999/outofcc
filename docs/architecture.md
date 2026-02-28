# Architecture

## 1. Searx-first retrieval backbone

The platform uses Searx as the upstream search aggregator:
1. API request arrives (`/v1/search` or `/v1/agent/context`)
2. Request validated + authenticated
3. Request sent to Searx via JSON API (`app/clients/searx_client.py`)
4. Results normalized and reranked
5. Cached response returned

## 2. Platform modules

- Search API module: API key auth, plan rate limits, cache, reranking
- Search Console module: site onboarding, ownership verification, analytics, issue board
- Agent Context module: structured context creation for LLMs/agents
- Dataset module: generated corpora for model pipelines
- Blog module: internal product update publishing workflow

## 3. Data model (SQLite, production-switchable)

- `users`, `api_keys`
- `sites`, `site_metrics`, `site_issues`
- `api_usage`
- `datasets`, `dataset_rows`
- `blog_posts`

## 4. Runtime paths

- UI routes: `/dashboard`, `/console`, `/agent`, `/blog`
- API routes: `/v1/search`, `/v1/agent/context`, `/v1/agent/datasets/create`

## 5. Production scale strategy

- Replace SQLite with Postgres
- Replace in-memory limiter/cache with Redis
- Run multi-worker ASGI and horizontal autoscaling
- Add async workers for verification probes, crawl telemetry, and issue generation

## Optimization updates

- Reduced route-level duplication in `app/main.py` via shared render/build helpers.
- Switched SQLite connection defaults to WAL + NORMAL sync + FK enforcement for better concurrent behavior.
- Switched bulk inserts to `executemany` for metrics and dataset rows to reduce DB overhead.
