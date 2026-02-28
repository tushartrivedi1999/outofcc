from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.security import hash_password


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class UserStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
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

                CREATE TABLE IF NOT EXISTS datasets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    source TEXT NOT NULL,
                    query TEXT NOT NULL,
                    rows_count INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(user_id, name),
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS dataset_rows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dataset_id INTEGER NOT NULL,
                    row_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    source_url TEXT,
                    UNIQUE(dataset_id, row_index),
                    FOREIGN KEY(dataset_id) REFERENCES datasets(id)
                );

                CREATE TABLE IF NOT EXISTS blog_posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    author_user_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    slug TEXT UNIQUE NOT NULL,
                    summary TEXT NOT NULL,
                    content_markdown TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(author_user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE NOT NULL,
                    plan TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    renewed_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    order_id TEXT NOT NULL,
                    payment_id TEXT,
                    signature TEXT,
                    amount_paise INTEGER NOT NULL,
                    currency TEXT NOT NULL,
                    plan TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );
                """
            )

    def create_user(self, username: str, password: str) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, hash_password(password), _utc_now_iso()),
            )
            return int(cur.lastrowid)

    def ensure_admin_user(self) -> None:
        if self.get_user_by_username("admin") is None:
            self.create_user("admin", "admin")

    def get_user_by_username(self, username: str) -> sqlite3.Row | None:
        with self._connect() as conn:
            return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

    def find_user_by_id(self, user_id: int) -> sqlite3.Row | None:
        with self._connect() as conn:
            return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    def create_api_key(self, user_id: int, key_hash: str, prefix: str, plan: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO api_keys (user_id, key_hash, prefix, plan, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, key_hash, prefix, plan, _utc_now_iso()),
            )

    def list_api_keys(self, user_id: int) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return list(
                conn.execute(
                    "SELECT prefix, plan, created_at FROM api_keys WHERE user_id = ? ORDER BY id DESC",
                    (user_id,),
                ).fetchall()
            )

    def find_api_key_by_hash(self, key_hash: str) -> sqlite3.Row | None:
        with self._connect() as conn:
            return conn.execute(
                "SELECT user_id, key_hash, plan FROM api_keys WHERE key_hash = ?",
                (key_hash,),
            ).fetchone()

    def create_site(self, user_id: int, domain: str, verification_token: str) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO sites (user_id, domain, verification_token, created_at) VALUES (?, ?, ?, ?)",
                (user_id, domain, verification_token, _utc_now_iso()),
            )
            return int(cur.lastrowid)

    def list_sites(self, user_id: int) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return list(
                conn.execute(
                    "SELECT id, domain, verified, verification_method, created_at FROM sites WHERE user_id = ? ORDER BY id DESC",
                    (user_id,),
                ).fetchall()
            )

    def find_site(self, site_id: int, user_id: int) -> sqlite3.Row | None:
        with self._connect() as conn:
            return conn.execute("SELECT * FROM sites WHERE id = ? AND user_id = ?", (site_id, user_id)).fetchone()

    def mark_site_verified(self, site_id: int, method: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE sites SET verified = 1, verification_method = ? WHERE id = ?", (method, site_id))

    def seed_site_metrics(self, site_id: int, metrics: list[dict[str, int | float | str]]) -> None:
        payload = [
            (
                site_id,
                str(row["metric_date"]),
                int(row["impressions"]),
                int(row["clicks"]),
                float(row["ctr"]),
                float(row["avg_position"]),
            )
            for row in metrics
        ]
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR IGNORE INTO site_metrics (site_id, metric_date, impressions, clicks, ctr, avg_position)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                payload,
            )

    def add_site_issue(self, site_id: int, issue_type: str, severity: str, status: str, details: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO site_issues (site_id, issue_type, severity, status, details, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (site_id, issue_type, severity, status, details, _utc_now_iso()),
            )

    def list_site_metrics(self, site_id: int) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return list(
                conn.execute(
                    "SELECT metric_date, impressions, clicks, ctr, avg_position FROM site_metrics WHERE site_id = ? ORDER BY metric_date",
                    (site_id,),
                ).fetchall()
            )

    def list_site_issues(self, site_id: int) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return list(
                conn.execute(
                    "SELECT issue_type, severity, status, details, created_at FROM site_issues WHERE site_id = ? ORDER BY id DESC",
                    (site_id,),
                ).fetchall()
            )

    def log_api_usage(self, user_id: int, query: str, took_ms: int, result_count: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO api_usage (user_id, request_at, query, took_ms, result_count) VALUES (?, ?, ?, ?, ?)",
                (user_id, _utc_now_iso(), query[:512], took_ms, result_count),
            )

    def list_recent_api_usage(self, user_id: int, limit: int = 30) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return list(
                conn.execute(
                    "SELECT request_at, query, took_ms, result_count FROM api_usage WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                    (user_id, limit),
                ).fetchall()
            )

    def create_dataset(self, user_id: int, name: str, source: str, query: str, rows_count: int) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO datasets (user_id, name, source, query, rows_count, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, name, source, query, rows_count, "ready", _utc_now_iso()),
            )
            return int(cur.lastrowid)

    def add_dataset_rows(self, dataset_id: int, rows: list[dict[str, str]]) -> None:
        payload = [(dataset_id, index, row.get("content", ""), row.get("source_url", "")) for index, row in enumerate(rows)]
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR IGNORE INTO dataset_rows (dataset_id, row_index, content, source_url)
                VALUES (?, ?, ?, ?)
                """,
                payload,
            )

    def list_datasets(self, user_id: int) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return list(
                conn.execute(
                    "SELECT id, name, source, query, rows_count, status, created_at FROM datasets WHERE user_id = ? ORDER BY id DESC",
                    (user_id,),
                ).fetchall()
            )

    def dataset_rows(self, dataset_id: int) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return list(
                conn.execute(
                    "SELECT row_index, content, source_url FROM dataset_rows WHERE dataset_id = ? ORDER BY row_index",
                    (dataset_id,),
                ).fetchall()
            )

    def create_blog_post(
        self,
        author_user_id: int,
        title: str,
        slug: str,
        summary: str,
        content_markdown: str,
        status: str = "published",
    ) -> int:
        now = _utc_now_iso()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO blog_posts (author_user_id, title, slug, summary, content_markdown, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (author_user_id, title, slug, summary, content_markdown, status, now, now),
            )
            return int(cur.lastrowid)

    def list_blog_posts(self, include_drafts: bool = True) -> list[sqlite3.Row]:
        with self._connect() as conn:
            if include_drafts:
                rows = conn.execute(
                    "SELECT id, title, slug, summary, status, created_at, updated_at FROM blog_posts ORDER BY id DESC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, title, slug, summary, status, created_at, updated_at FROM blog_posts WHERE status = 'published' ORDER BY id DESC"
                ).fetchall()
            return list(rows)

    def find_blog_post_by_slug(self, slug: str) -> sqlite3.Row | None:
        with self._connect() as conn:
            return conn.execute(
                "SELECT id, title, slug, summary, content_markdown, status, created_at, updated_at FROM blog_posts WHERE slug = ?",
                (slug,),
            ).fetchone()


    def search_calls_today(self, user_id: int) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM api_usage
                WHERE user_id = ?
                  AND substr(request_at, 1, 10) = date('now')
                """,
                (user_id,),
            ).fetchone()
            return int(row["c"]) if row else 0

    def get_subscription(self, user_id: int) -> sqlite3.Row | None:
        with self._connect() as conn:
            return conn.execute(
                "SELECT user_id, plan, status, started_at, renewed_at FROM subscriptions WHERE user_id = ?",
                (user_id,),
            ).fetchone()

    def upsert_subscription(self, user_id: int, plan: str, status: str = "active") -> None:
        now = _utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO subscriptions (user_id, plan, status, started_at, renewed_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    plan = excluded.plan,
                    status = excluded.status,
                    renewed_at = excluded.renewed_at
                """,
                (user_id, plan, status, now, now),
            )

    def create_payment_record(self, user_id: int, order_id: str, amount_paise: int, currency: str, plan: str, status: str = "created") -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO payments (user_id, order_id, amount_paise, currency, plan, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, order_id, amount_paise, currency, plan, status, _utc_now_iso()),
            )
            return int(cur.lastrowid)

    def complete_payment(self, order_id: str, payment_id: str, signature: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE payments
                SET payment_id = ?, signature = ?, status = 'captured'
                WHERE order_id = ?
                """,
                (payment_id, signature, order_id),
            )

    def list_payments(self, user_id: int, limit: int = 20) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return list(
                conn.execute(
                    "SELECT order_id, payment_id, amount_paise, currency, plan, status, created_at FROM payments WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                    (user_id, limit),
                ).fetchall()
            )

