# Integration Guide (Step-by-Step)

This guide explains how to integrate the project into an existing search or AI-agent product.

## 1) Boot the platform

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
set -a && source .env && set +a
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 2) Create account and API key

1. Open `http://localhost:8000/login`
2. Login with `admin/admin` or create your own user at `/signup`
3. Open `/dashboard`
4. Generate a plan-based API key

## 3) Integrate search API into your app

Use `POST /v1/search` with `Authorization: Bearer <API_KEY>`.

## 4) Integrate agent-grounding context API (Tavily alternative)

Use `POST /v1/agent/context` to receive structured web context:
- short answer brief
- citations
- normalized context chunks
- freshness hint

## 5) Integrate dataset generation API

Use `POST /v1/agent/datasets/create` to create datasets from:
- `open-search`
- `commoncrawl` (connector-style simulated rows in current build)

## 6) Enable Search Console workflows for your users

1. Open `/console`
2. Add property
3. Verify via DNS or URL-prefix token
4. Inspect analytics and issue tables

## 7) Production checklist

- Replace SQLite with Postgres
- Replace in-memory cache/ratelimiter with Redis
- Add background workers for crawl and metrics ingestion
- Add proper external DNS/file verification probes
- Add billing + quotas + abuse controls
