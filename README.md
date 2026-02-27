# Open Search API + Open Search Console

Production-oriented Python platform combining:
1. **Search API layer** (Google Search API alternative)
2. **Open Search Console layer** (Google Search Console-style website onboarding, verification, performance analytics, and issue tracking)

## Core modules

- `app/main.py`: FastAPI routes for auth, dashboard, API key management, search API, and Search Console
- `app/clients/searx_client.py`: Searx backend connector
- `app/service.py`: retrieval + reranking + cache orchestration
- `app/user_store.py`: SQLite persistence for users, API keys, properties, metrics, issues
- `app/console.py`: Search Console verification payloads + analytics chart generation
- `templates/`: UI for dashboard, console property list, verification, and analytics views
- `sdk/python/opensearch_sdk.py`: Python SDK for `/v1/search`
- `scripts/load_test.py`: stress/load test with distortion detection

## Features

### Search API platform
- API key issuance (`free`, `pro`, `enterprise`)
- Plan-aware rate limiting
- In-memory TTL caching
- Result reranking (relevance + freshness)
- Searx retrieval integration

### Open Search Console (Google Search Console-style)
- Add website property (domain / URL prefix)
- Ownership verification workflow:
  - DNS TXT method
  - URL-prefix file method
- Property status (pending/verified)
- Performance analytics:
  - Impressions graph
  - Clicks graph
  - CTR / average position table
- Quality and indexing issues board

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
set -a && source .env && set +a
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open:
- `http://localhost:8000/login`
- default bootstrap account: `admin` / `admin`
- dashboard: `http://localhost:8000/dashboard`
- Search Console: `http://localhost:8000/console`

## API usage

Generate an API key in dashboard, then call:

```bash
curl -X POST http://localhost:8000/v1/search \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"q":"best python web framework", "num_results": 5, "language":"en"}'
```

## Python SDK integration

```python
from sdk.python.opensearch_sdk import OpenSearchSDK

client = OpenSearchSDK(base_url="http://localhost:8000", api_key="<YOUR_API_KEY>")
print(client.search("open source search engine", num_results=5))
```

## Search Console integration flow for users

1. Sign in and open `/console`.
2. Add property (domain or URL prefix).
3. Open property detail and choose verification method.
4. Apply DNS TXT or upload verification file.
5. Submit verification token in UI to mark property verified.
6. After verification, inspect performance charts and issues table.

## Stress / load testing

```bash
python scripts/load_test.py --base-url http://localhost:8000 --api-key <YOUR_API_KEY> --concurrency 50 --requests 2000
```

The tool reports:
- success/failure count
- distorted payload count
- status code distribution
- throughput + p50/p95/p99 latency

Exit code is non-zero when payload distortion or request failures are detected.

## Configuration

- `SEARX_BASE_URL`
- `REQUEST_TIMEOUT_S`
- `CACHE_TTL_S`
- `FREE_RPM`, `PRO_RPM`, `ENTERPRISE_RPM`
- `SESSION_SECRET`
- `DB_PATH`

## Production hardening recommendations

- replace SQLite with Postgres for multi-node deployments
- replace in-process rate limiter/cache with Redis
- add background crawlers and real site telemetry ingestion for metrics
- implement stronger verification checks (actual DNS/file fetch validation)
- add RBAC, audit logs, billing, and abuse detection

## Push to GitHub

If no remote is configured:

```bash
git remote add origin https://github.com/<your-org-or-user>/<repo>.git
git push -u origin <your-branch>
```

Otherwise:

```bash
git push
```
