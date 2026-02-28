# Security Overview

## Controls implemented

- Password hashing: PBKDF2-HMAC with per-user salt
- Session integrity: HMAC-signed, expiring cookie token
- API key storage: SHA-256 hash only
- Rate limit guardrails by plan tier

## Recommended hardening

- Secret rotation and vault integration
- CSRF defense for form endpoints
- SQL migration framework + schema versioning
- RBAC with scoped tokens
- WAF + abuse detection + anomaly alerts
- Full audit log pipeline
