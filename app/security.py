from __future__ import annotations

import hashlib
import hmac
import os
import secrets


def hash_password(password: str, salt: bytes | None = None) -> str:
    current_salt = salt or os.urandom(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), current_salt, 200_000)
    return f"{current_salt.hex()}:{derived.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        salt_hex, digest_hex = encoded.split(":", maxsplit=1)
    except ValueError:
        return False
    candidate = hash_password(password, bytes.fromhex(salt_hex)).split(":", maxsplit=1)[1]
    return hmac.compare_digest(candidate, digest_hex)


def generate_api_key() -> str:
    return "osk_" + secrets.token_urlsafe(32)
