# Open Search API Platform

A practical, production-minded Python service that can power a free/paid search API business with Searx as retrieval backend.

## What this project now includes

- FastAPI HTTP API for search (`/v1/search`)
- Authentication portal with server-rendered templates:
  - Landing page (`/`)
  - Signup (`/signup`)
  - Login (`/login`)
  - Dashboard (`/dashboard`) to generate API keys
- Default bootstrap account: `admin` / `admin`
- API key hashing + persistence in SQLite
- Plan-aware rate limiting (`free`, `pro`, `enterprise`)
- In-memory TTL response cache and reranking layer
- Python SDK (`sdk/python/opensearch_sdk.py`)
- Load-test utility (`scripts/load_test.py`)

## Architecture

1. **Retrieval layer**: `SearxClient` queries your Searx instance over JSON.
2. **Optimization layer**: cache + reranking improve latency and relevance stability.
3. **Access layer**: auth portal issues API keys; search endpoint validates key + plan limits.
4. **Developer layer**: SDK and docs for quick third-party adoption.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
set -a && source .env && set +a
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Visit:

- `http://localhost:8000/` (landing)
- `http://localhost:8000/login` (login, default `admin/admin`)
- `http://localhost:8000/dashboard` (generate API keys)

## Use API key

```bash
curl -X POST http://localhost:8000/v1/search \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"q":"latest llm benchmarks", "num_results": 5, "language":"en"}'
```

## Python SDK usage

```python
from sdk.python.opensearch_sdk import OpenSearchSDK

client = OpenSearchSDK(base_url="http://localhost:8000", api_key="<YOUR_API_KEY>")
print(client.search("fastapi tutorial", num_results=3))
```

## Load testing

Run with CLI options (recommended):

```bash
python scripts/load_test.py --base-url http://localhost:8000 --api-key <YOUR_API_KEY> --concurrency 50 --requests 2000
```

The script validates payload shape and reports:
- success/failure counts
- distorted response count
- status-code distribution
- throughput + p50/p95/p99 latency

Exit code is non-zero if failures or distorted payloads are detected.

## Configuration

- `SEARX_BASE_URL` (default `http://localhost:8080`)
- `REQUEST_TIMEOUT_S` (default `7.0`)
- `CACHE_TTL_S` (default `60`)
- `FREE_RPM`, `PRO_RPM`, `ENTERPRISE_RPM`
- `SESSION_SECRET` (set a strong secret in production)
- `DB_PATH` (default `data/app.db`)

## How to modify safely

- Add new providers under `app/clients/` and merge/fallback in `SearchService`.
- Move in-memory rate limiter to Redis for multi-instance deployments.
- Move SQLite to Postgres for HA workloads.
- Add billing hooks around API-key issuance and request metering.

## Key engineering decisions

- Passwords use PBKDF2-HMAC with high iteration count.
- API keys are stored as SHA-256 hashes only.
- Session cookie is HMAC-signed and time-limited.
- Auth and API key generation are isolated from search execution path.


## Push to GitHub

If your local repo has no remote configured yet:

```bash
git remote add origin https://github.com/<your-org-or-user>/<repo>.git
git push -u origin <your-branch>
```

If a remote already exists, just push:

```bash
git push
```
