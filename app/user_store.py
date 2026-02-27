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

                CREATE TABLE IF NOT EXISTS sites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    domain TEXT NOT NULL,
                    verification_token TEXT NOT NULL,
                    verified INTEGER NOT NULL DEFAULT 0,
                    verification_method TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(user_id, domain),
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS site_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    site_id INTEGER NOT NULL,
                    metric_date TEXT NOT NULL,
                    impressions INTEGER NOT NULL,
                    clicks INTEGER NOT NULL,
                    ctr REAL NOT NULL,
                    avg_position REAL NOT NULL,
                    UNIQUE(site_id, metric_date),
                    FOREIGN KEY(site_id) REFERENCES sites(id)
                );

                CREATE TABLE IF NOT EXISTS site_issues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    site_id INTEGER NOT NULL,
                    issue_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    details TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(site_id) REFERENCES sites(id)
                );


                CREATE TABLE IF NOT EXISTS api_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    request_at TEXT NOT NULL,
                    query TEXT NOT NULL,
                    took_ms INTEGER NOT NULL,
                    result_count INTEGER NOT NULL,
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

    def create_site(self, user_id: int, domain: str, verification_token: str) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO sites (user_id, domain, verification_token, created_at) VALUES (?, ?, ?, ?)",
                (user_id, domain, verification_token, now),
            )
            return int(cur.lastrowid)

    def list_sites(self, user_id: int) -> list[sqlite3.Row]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, domain, verified, verification_method, created_at FROM sites WHERE user_id = ? ORDER BY id DESC",
                (user_id,),
            ).fetchall()
            return list(rows)

    def find_site(self, site_id: int, user_id: int) -> sqlite3.Row | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sites WHERE id = ? AND user_id = ?",
                (site_id, user_id),
            ).fetchone()
            return row

    def mark_site_verified(self, site_id: int, method: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE sites SET verified = 1, verification_method = ? WHERE id = ?",
                (method, site_id),
            )

    def seed_site_metrics(self, site_id: int, metrics: list[dict[str, int | float | str]]) -> None:
        with self._connect() as conn:
            for row in metrics:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO site_metrics (site_id, metric_date, impressions, clicks, ctr, avg_position)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        site_id,
                        str(row["metric_date"]),
                        int(row["impressions"]),
                        int(row["clicks"]),
                        float(row["ctr"]),
                        float(row["avg_position"]),
                    ),
                )

    def add_site_issue(self, site_id: int, issue_type: str, severity: str, status: str, details: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO site_issues (site_id, issue_type, severity, status, details, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (site_id, issue_type, severity, status, details, now),
            )

    def list_site_metrics(self, site_id: int) -> list[sqlite3.Row]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT metric_date, impressions, clicks, ctr, avg_position FROM site_metrics WHERE site_id = ? ORDER BY metric_date",
                (site_id,),
            ).fetchall()
            return list(rows)

    def list_site_issues(self, site_id: int) -> list[sqlite3.Row]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT issue_type, severity, status, details, created_at FROM site_issues WHERE site_id = ? ORDER BY id DESC",
                (site_id,),
            ).fetchall()
            return list(rows)


    def log_api_usage(self, user_id: int, query: str, took_ms: int, result_count: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO api_usage (user_id, request_at, query, took_ms, result_count) VALUES (?, ?, ?, ?, ?)",
                (user_id, now, query[:512], took_ms, result_count),
            )

    def list_recent_api_usage(self, user_id: int, limit: int = 30) -> list[sqlite3.Row]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT request_at, query, took_ms, result_count FROM api_usage WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
            return list(rows)
