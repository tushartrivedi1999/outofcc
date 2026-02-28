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

## Stress and load

Use:

```bash
python scripts/load_test.py --base-url http://localhost:8000 --api-key <KEY> --concurrency 50 --requests 2000
```

Metrics:
- success/failure
- distortion count
- status distribution
- p50/p95/p99 latency

## Monkey testing

Use randomized input tests against store/services:

```bash
python scripts/monkey_test.py
```

## Load-balance simulation

Use internal simulation utility:

```bash
python scripts/load_balance_test.py
```

## Production readiness checklist

- [ ] Postgres + Redis migration
- [ ] HTTPS and secret-management hardening
- [ ] Monitoring (metrics/logs/traces)
- [ ] Autoscaling and health checks
- [ ] Background workers for telemetry and verification probes
