# Security Overview

## Controls implemented

- Password hashing: PBKDF2-HMAC with per-user salt
- Session integrity: HMAC-signed, expiring cookie token
- API key storage: SHA-256 hash only
- Rate limit guardrails by plan tier
- CSRF token defense for authenticated form POST routes
- Billing capture idempotency + signed webhook verification
- Structured request logging with request IDs

## Recommended hardening

- Secret rotation and vault integration
- Baseline schema version tracking (`schema_migrations`) and additive backfill migrations
- RBAC with scoped tokens
- WAF + abuse detection + anomaly alerts
- Full audit log pipeline
