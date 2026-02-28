# Integration Guide (Step-by-Step)

This guide explains how to integrate the platform into an existing search or AI product.

## 1) Boot the platform

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
set -a && source .env && set +a
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 2) Configure Searx and billing

In `.env`:
- set `SEARX_BASE_URL`
- set Razorpay credentials (`RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`)
- free quota is controlled by `FREE_DAILY_CALLS` (default 500/day)

## 3) User onboarding and key issuance

1. Login at `/login` (`admin/admin` bootstrap)
2. Open `/dashboard`
3. Generate a `free` key immediately
4. To generate `pro`/`enterprise` keys, open `/billing` and activate subscription

## 4) Free quota and upgrades

- `free` API keys are limited to `FREE_DAILY_CALLS` search calls/day (default 500)
- once exceeded, API returns payment-required response
- use `/billing` to create and verify Razorpay payments, then generate higher-plan keys

## 5) Integrate APIs

- Search: `POST /v1/search`
- Agent context: `POST /v1/agent/context`
- Dataset creation: `POST /v1/agent/datasets/create`

## 6) Search Console usage

1. Open `/console`
2. Add property
3. Verify by DNS or URL-prefix token
4. Use analytics + issue tables

## 7) Internal blog workflow

- Publish updates at `/blog/new`
- Read posts at `/blog`
- Use this for product release communication

## 8) Production checklist

- Postgres + Redis migration
- async verification workers
- webhook-based Razorpay verification flow
- observability, RBAC, billing analytics, abuse controls

## 9) Optimization notes

- Reused helper paths reduce repeated logic in route handlers.
- SQLite now includes indexes for API usage, payments, sites, datasets, and blog slug lookups.
- Keep `FREE_DAILY_CALLS` and plan RPM values aligned with your commercial policy.

