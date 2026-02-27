from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.security import hash_password


class UserStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    key_hash TEXT UNIQUE NOT NULL,
                    prefix TEXT NOT NULL,
                    plan TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );
                """
            )

    def create_user(self, username: str, password: str) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, hash_password(password), now),
            )
            return int(cur.lastrowid)

    def ensure_admin_user(self) -> None:
        if self.get_user_by_username("admin") is None:
            self.create_user("admin", "admin")

    def get_user_by_username(self, username: str) -> sqlite3.Row | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            return row

    def find_user_by_id(self, user_id: int) -> sqlite3.Row | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return row

    def create_api_key(self, user_id: int, key_hash: str, prefix: str, plan: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO api_keys (user_id, key_hash, prefix, plan, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, key_hash, prefix, plan, now),
            )

    def list_api_keys(self, user_id: int) -> list[sqlite3.Row]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT prefix, plan, created_at FROM api_keys WHERE user_id = ? ORDER BY id DESC",
                (user_id,),
            ).fetchall()
            return list(rows)

    def find_api_key_by_hash(self, key_hash: str) -> sqlite3.Row | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT user_id, key_hash, plan FROM api_keys WHERE key_hash = ?",
                (key_hash,),
            ).fetchone()
            return row
