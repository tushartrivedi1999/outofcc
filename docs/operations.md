# Operations, Stress, Monkey and Load-Balance Testing

## Runbook

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
set -a && source .env && set +a
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Billing setup (Razorpay)

Set env vars:
- `RAZORPAY_KEY_ID`
- `RAZORPAY_KEY_SECRET`
- `PAYMENT_CURRENCY`
- `PRO_MONTHLY_PRICE_INR`
- `ENTERPRISE_MONTHLY_PRICE_INR`

Then use `/billing` route for order creation and payment verification.

## Stress and load

```bash
python scripts/load_test.py --base-url http://localhost:8000 --api-key <KEY> --concurrency 50 --requests 2000
```

## Monkey testing

```bash
python scripts/monkey_test.py
```

## Load-balance simulation

```bash
python scripts/load_balance_test.py
```

## Production readiness checklist

- [ ] Postgres + Redis migration
- [ ] HTTPS and secret-management hardening
- [ ] Monitoring (metrics/logs/traces)
- [ ] Autoscaling and health checks
- [ ] Background workers for telemetry and verification probes
- [ ] Razorpay webhook pipeline for async payment state updates

## Performance tuning notes

- SQLite uses WAL mode for better read/write concurrency.
- Batch writes use `executemany`.
- Free plan daily quota guard is DB-count based per UTC day.
- SQLite query paths are index-backed for common user/day and user/payment lookups.
- Set `DB_BACKEND=postgres` + `DB_DSN` to run with PostgreSQL in production.

