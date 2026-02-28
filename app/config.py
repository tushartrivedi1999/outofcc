from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    searx_base_url: str = os.getenv("SEARX_BASE_URL", "http://localhost:8080")
    request_timeout_s: float = float(os.getenv("REQUEST_TIMEOUT_S", "7.0"))
    cache_ttl_s: int = int(os.getenv("CACHE_TTL_S", "60"))
    free_rpm: int = int(os.getenv("FREE_RPM", "30"))
    pro_rpm: int = int(os.getenv("PRO_RPM", "300"))
    enterprise_rpm: int = int(os.getenv("ENTERPRISE_RPM", "3000"))
    session_secret: str = os.getenv("SESSION_SECRET", "change-me-in-prod")
    db_backend: str = os.getenv("DB_BACKEND", "sqlite").lower()
    db_path: str = os.getenv("DB_PATH", "data/app.db")
    db_dsn: str = os.getenv("DB_DSN", "")
    free_daily_calls: int = int(os.getenv("FREE_DAILY_CALLS", "500"))
    razorpay_key_id: str = os.getenv("RAZORPAY_KEY_ID", "")
    razorpay_key_secret: str = os.getenv("RAZORPAY_KEY_SECRET", "")
    payment_currency: str = os.getenv("PAYMENT_CURRENCY", "INR")
    pro_monthly_price_inr: int = int(os.getenv("PRO_MONTHLY_PRICE_INR", "999"))
    enterprise_monthly_price_inr: int = int(os.getenv("ENTERPRISE_MONTHLY_PRICE_INR", "4999"))


SETTINGS = Settings()
