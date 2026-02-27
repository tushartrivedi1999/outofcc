from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time


class SessionManager:
    def __init__(self, secret: str, max_age_s: int = 86_400) -> None:
        self._secret = secret.encode("utf-8")
        self._max_age_s = max_age_s

    def create(self, user_id: int) -> str:
        payload = {"user_id": user_id, "exp": int(time.time()) + self._max_age_s}
        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        body = base64.urlsafe_b64encode(raw).decode("utf-8")
        sig = hmac.new(self._secret, body.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{body}.{sig}"

    def verify(self, token: str | None) -> int | None:
        if not token or "." not in token:
            return None
        body, signature = token.split(".", maxsplit=1)
        expected = hmac.new(self._secret, body.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        try:
            payload = json.loads(base64.urlsafe_b64decode(body.encode("utf-8")))
        except Exception:
            return None
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return int(payload.get("user_id", 0)) or None
