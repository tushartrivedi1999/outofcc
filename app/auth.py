from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from app.domain import Plan
from app.user_store import UserStore


@dataclass(frozen=True)
class ApiPrincipal:
    key_hash: str
    plan: Plan
    user_id: int


class KeyStore:
    """Database-backed key lookup for API authentication."""

    def __init__(self, user_store: UserStore) -> None:
        self._user_store = user_store

    @staticmethod
    def _hash_key(raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def authenticate(self, token: str | None) -> ApiPrincipal | None:
        if not token:
            return None
        digest = self._hash_key(token)
        row = self._user_store.find_api_key_by_hash(digest)
        if row is None:
            return None
        if not hmac.compare_digest(row["key_hash"], digest):
            return None
        return ApiPrincipal(key_hash=row["key_hash"], plan=Plan(row["plan"]), user_id=row["user_id"])
