from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.security import hash_password


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class UserStore:
    def __init__(self, db_path: str, backend: str = "sqlite", dsn: str = "") -> None:
        self._backend = backend.lower()
        self._db_path = db_path
        self._dsn = dsn
        if self._backend == "sqlite":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        if self._backend == "sqlite":
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            return conn

        if self._backend in {"postgres", "postgresql", "sql"}:
            try:
                import psycopg
                from psycopg.rows import dict_row
            except Exception as exc:  # pragma: no cover
                raise RuntimeError("Postgres backend requires psycopg package") from exc
            if not self._dsn:
                raise RuntimeError("DB_DSN must be provided for postgres backend")
            return psycopg.connect(self._dsn, row_factory=dict_row)

        raise RuntimeError(f"Unsupported DB_BACKEND: {self._backend}")

    def _sql(self, statement: str) -> str:
        if self._backend == "sqlite":
            return statement
        return statement.replace("?", "%s")

    def _execute(self, statement: str, params: tuple[Any, ...] = ()):
        with self._connect() as conn:
            cur = conn.execute(self._sql(statement), params)
            if self._backend != "sqlite":
                conn.commit()
            return cur

    def _fetchone(self, statement: str, params: tuple[Any, ...] = ()):
        with self._connect() as conn:
            cur = conn.execute(self._sql(statement), params)
            row = cur.fetchone()
            return row

    def _fetchall(self, statement: str, params: tuple[Any, ...] = ()) -> list:
        with self._connect() as conn:
            cur = conn.execute(self._sql(statement), params)
            return list(cur.fetchall())

    def _init_db(self) -> None:
        with self._connect() as conn:
            if self._backend == "sqlite":
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version TEXT PRIMARY KEY,
                        applied_at TEXT NOT NULL
                    );
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
                        order_id TEXT UNIQUE NOT NULL,
                        payment_id TEXT,
                        signature TEXT,
                        webhook_event_id TEXT,
                        amount_paise INTEGER NOT NULL,
                        currency TEXT NOT NULL,
                        plan TEXT NOT NULL,
                        status TEXT NOT NULL,
                        processed_at TEXT,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(user_id) REFERENCES users(id)
                    );
                    CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id);
                    CREATE INDEX IF NOT EXISTS idx_sites_user ON sites(user_id);
                    CREATE INDEX IF NOT EXISTS idx_site_metrics_site_date ON site_metrics(site_id, metric_date);
                    CREATE INDEX IF NOT EXISTS idx_site_issues_site ON site_issues(site_id);
                    CREATE INDEX IF NOT EXISTS idx_api_usage_user_day ON api_usage(user_id, request_at);
                    CREATE INDEX IF NOT EXISTS idx_datasets_user ON datasets(user_id);
                    CREATE INDEX IF NOT EXISTS idx_blog_slug ON blog_posts(slug);
                    CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id);
                    CREATE INDEX IF NOT EXISTS idx_payments_user_created ON payments(user_id, created_at);
                    CREATE INDEX IF NOT EXISTS idx_payments_order ON payments(order_id);
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_payment_id_unique ON payments(payment_id) WHERE payment_id IS NOT NULL;
                    """
                )
                return

            statements = [
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS users (
                    id BIGSERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS api_keys (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id),
                    key_hash TEXT UNIQUE NOT NULL,
                    prefix TEXT NOT NULL,
                    plan TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS sites (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id),
                    domain TEXT NOT NULL,
                    verification_token TEXT NOT NULL,
                    verified INTEGER NOT NULL DEFAULT 0,
                    verification_method TEXT,
                    created_at TIMESTAMPTZ NOT NULL,
                    UNIQUE(user_id, domain)
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS site_metrics (
                    id BIGSERIAL PRIMARY KEY,
                    site_id BIGINT NOT NULL REFERENCES sites(id),
                    metric_date TEXT NOT NULL,
                    impressions INTEGER NOT NULL,
                    clicks INTEGER NOT NULL,
                    ctr DOUBLE PRECISION NOT NULL,
                    avg_position DOUBLE PRECISION NOT NULL,
                    UNIQUE(site_id, metric_date)
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS site_issues (
                    id BIGSERIAL PRIMARY KEY,
                    site_id BIGINT NOT NULL REFERENCES sites(id),
                    issue_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    details TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS api_usage (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id),
                    request_at TIMESTAMPTZ NOT NULL,
                    query TEXT NOT NULL,
                    took_ms INTEGER NOT NULL,
                    result_count INTEGER NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS datasets (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id),
                    name TEXT NOT NULL,
                    source TEXT NOT NULL,
                    query TEXT NOT NULL,
                    rows_count INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    UNIQUE(user_id, name)
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS dataset_rows (
                    id BIGSERIAL PRIMARY KEY,
                    dataset_id BIGINT NOT NULL REFERENCES datasets(id),
                    row_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    source_url TEXT,
                    UNIQUE(dataset_id, row_index)
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS blog_posts (
                    id BIGSERIAL PRIMARY KEY,
                    author_user_id BIGINT NOT NULL REFERENCES users(id),
                    title TEXT NOT NULL,
                    slug TEXT UNIQUE NOT NULL,
                    summary TEXT NOT NULL,
                    content_markdown TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT UNIQUE NOT NULL REFERENCES users(id),
                    plan TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TIMESTAMPTZ NOT NULL,
                    renewed_at TIMESTAMPTZ NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS payments (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id),
                    order_id TEXT UNIQUE NOT NULL,
                    payment_id TEXT UNIQUE,
                    signature TEXT,
                    webhook_event_id TEXT,
                    amount_paise INTEGER NOT NULL,
                    currency TEXT NOT NULL,
                    plan TEXT NOT NULL,
                    status TEXT NOT NULL,
                    processed_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """,
                "CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_sites_user ON sites(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_site_metrics_site_date ON site_metrics(site_id, metric_date)",
                "CREATE INDEX IF NOT EXISTS idx_site_issues_site ON site_issues(site_id)",
                "CREATE INDEX IF NOT EXISTS idx_api_usage_user_day ON api_usage(user_id, request_at)",
                "CREATE INDEX IF NOT EXISTS idx_datasets_user ON datasets(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_blog_slug ON blog_posts(slug)",
                "CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_payments_user_created ON payments(user_id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_payments_order ON payments(order_id)",
            ]
            for statement in statements:
                conn.execute(statement)
            conn.commit()

        self._apply_backfill_migrations()
        self._record_migration("2026_02_baseline")

    def _record_migration(self, version: str) -> None:
        now = _utc_now_iso()
        with self._connect() as conn:
            if self._backend == "sqlite":
                conn.execute(
                    "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                    (version, now),
                )
                return
            conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (%s, %s) ON CONFLICT(version) DO NOTHING",
                (version, now),
            )
            conn.commit()

    def _apply_backfill_migrations(self) -> None:
        with self._connect() as conn:
            if self._backend == "sqlite":
                for statement in [
                    "ALTER TABLE payments ADD COLUMN webhook_event_id TEXT",
                    "ALTER TABLE payments ADD COLUMN processed_at TEXT",
                    "CREATE INDEX IF NOT EXISTS idx_payments_order ON payments(order_id)",
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_payment_id_unique ON payments(payment_id) WHERE payment_id IS NOT NULL",
                ]:
                    try:
                        conn.execute(statement)
                    except Exception:
                        pass
                return
            conn.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS webhook_event_id TEXT")
            conn.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS processed_at TIMESTAMPTZ")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_order ON payments(order_id)")
            conn.commit()

    def create_user(self, username: str, password: str) -> int:
        now = _utc_now_iso()
        with self._connect() as conn:
            if self._backend == "sqlite":
                cur = conn.execute(
                    "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                    (username, hash_password(password), now),
                )
                return int(cur.lastrowid)
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (%s, %s, %s) RETURNING id",
                (username, hash_password(password), now),
            )
            new_id = int(cur.fetchone()["id"])
            conn.commit()
            return new_id

    def ensure_admin_user(self) -> None:
        if self.get_user_by_username("admin") is None:
            self.create_user("admin", "admin")

    def get_user_by_username(self, username: str):
        return self._fetchone("SELECT * FROM users WHERE username = ?", (username,))

    def find_user_by_id(self, user_id: int):
        return self._fetchone("SELECT * FROM users WHERE id = ?", (user_id,))

    def create_api_key(self, user_id: int, key_hash: str, prefix: str, plan: str) -> None:
        self._execute(
            "INSERT INTO api_keys (user_id, key_hash, prefix, plan, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, key_hash, prefix, plan, _utc_now_iso()),
        )

    def list_api_keys(self, user_id: int) -> list:
        return self._fetchall("SELECT prefix, plan, created_at FROM api_keys WHERE user_id = ? ORDER BY id DESC", (user_id,))

    def find_api_key_by_hash(self, key_hash: str):
        return self._fetchone("SELECT user_id, key_hash, plan FROM api_keys WHERE key_hash = ?", (key_hash,))

    def create_site(self, user_id: int, domain: str, verification_token: str) -> int:
        now = _utc_now_iso()
        with self._connect() as conn:
            if self._backend == "sqlite":
                cur = conn.execute(
                    "INSERT INTO sites (user_id, domain, verification_token, created_at) VALUES (?, ?, ?, ?)",
                    (user_id, domain, verification_token, now),
                )
                return int(cur.lastrowid)
            cur = conn.execute(
                "INSERT INTO sites (user_id, domain, verification_token, created_at) VALUES (%s, %s, %s, %s) RETURNING id",
                (user_id, domain, verification_token, now),
            )
            new_id = int(cur.fetchone()["id"])
            conn.commit()
            return new_id

    def list_sites(self, user_id: int) -> list:
        return self._fetchall(
            "SELECT id, domain, verified, verification_method, created_at FROM sites WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        )

    def find_site(self, site_id: int, user_id: int):
        return self._fetchone("SELECT * FROM sites WHERE id = ? AND user_id = ?", (site_id, user_id))

    def mark_site_verified(self, site_id: int, method: str) -> None:
        self._execute("UPDATE sites SET verified = 1, verification_method = ? WHERE id = ?", (method, site_id))

    def seed_site_metrics(self, site_id: int, metrics: list[dict[str, int | float | str]]) -> None:
        values = [
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
            if self._backend == "sqlite":
                conn.executemany(
                    """
                    INSERT OR IGNORE INTO site_metrics (site_id, metric_date, impressions, clicks, ctr, avg_position)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    values,
                )
                return
            conn.executemany(
                """
                INSERT INTO site_metrics (site_id, metric_date, impressions, clicks, ctr, avg_position)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT(site_id, metric_date) DO NOTHING
                """,
                values,
            )
            conn.commit()

    def add_site_issue(self, site_id: int, issue_type: str, severity: str, status: str, details: str) -> None:
        self._execute(
            "INSERT INTO site_issues (site_id, issue_type, severity, status, details, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (site_id, issue_type, severity, status, details, _utc_now_iso()),
        )

    def list_site_metrics(self, site_id: int) -> list:
        return self._fetchall(
            "SELECT metric_date, impressions, clicks, ctr, avg_position FROM site_metrics WHERE site_id = ? ORDER BY metric_date",
            (site_id,),
        )

    def list_site_issues(self, site_id: int) -> list:
        return self._fetchall(
            "SELECT issue_type, severity, status, details, created_at FROM site_issues WHERE site_id = ? ORDER BY id DESC",
            (site_id,),
        )

    def log_api_usage(self, user_id: int, query: str, took_ms: int, result_count: int) -> None:
        self._execute(
            "INSERT INTO api_usage (user_id, request_at, query, took_ms, result_count) VALUES (?, ?, ?, ?, ?)",
            (user_id, _utc_now_iso(), query[:512], took_ms, result_count),
        )

    def list_recent_api_usage(self, user_id: int, limit: int = 30) -> list:
        return self._fetchall(
            "SELECT request_at, query, took_ms, result_count FROM api_usage WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        )

    def create_dataset(self, user_id: int, name: str, source: str, query: str, rows_count: int) -> int:
        now = _utc_now_iso()
        with self._connect() as conn:
            if self._backend == "sqlite":
                cur = conn.execute(
                    "INSERT INTO datasets (user_id, name, source, query, rows_count, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (user_id, name, source, query, rows_count, "ready", now),
                )
                return int(cur.lastrowid)
            cur = conn.execute(
                "INSERT INTO datasets (user_id, name, source, query, rows_count, status, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (user_id, name, source, query, rows_count, "ready", now),
            )
            new_id = int(cur.fetchone()["id"])
            conn.commit()
            return new_id

    def add_dataset_rows(self, dataset_id: int, rows: list[dict[str, str]]) -> None:
        values = [(dataset_id, index, row.get("content", ""), row.get("source_url", "")) for index, row in enumerate(rows)]
        with self._connect() as conn:
            if self._backend == "sqlite":
                conn.executemany(
                    "INSERT OR IGNORE INTO dataset_rows (dataset_id, row_index, content, source_url) VALUES (?, ?, ?, ?)",
                    values,
                )
                return
            conn.executemany(
                """
                INSERT INTO dataset_rows (dataset_id, row_index, content, source_url)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT(dataset_id, row_index) DO NOTHING
                """,
                values,
            )
            conn.commit()

    def list_datasets(self, user_id: int) -> list:
        return self._fetchall(
            "SELECT id, name, source, query, rows_count, status, created_at FROM datasets WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        )

    def dataset_rows(self, dataset_id: int) -> list:
        return self._fetchall(
            "SELECT row_index, content, source_url FROM dataset_rows WHERE dataset_id = ? ORDER BY row_index",
            (dataset_id,),
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
            if self._backend == "sqlite":
                cur = conn.execute(
                    "INSERT INTO blog_posts (author_user_id, title, slug, summary, content_markdown, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (author_user_id, title, slug, summary, content_markdown, status, now, now),
                )
                return int(cur.lastrowid)
            cur = conn.execute(
                "INSERT INTO blog_posts (author_user_id, title, slug, summary, content_markdown, status, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (author_user_id, title, slug, summary, content_markdown, status, now, now),
            )
            new_id = int(cur.fetchone()["id"])
            conn.commit()
            return new_id

    def list_blog_posts(self, include_drafts: bool = True) -> list:
        if include_drafts:
            return self._fetchall("SELECT id, title, slug, summary, status, created_at, updated_at FROM blog_posts ORDER BY id DESC")
        return self._fetchall(
            "SELECT id, title, slug, summary, status, created_at, updated_at FROM blog_posts WHERE status = 'published' ORDER BY id DESC"
        )

    def find_blog_post_by_slug(self, slug: str):
        return self._fetchone(
            "SELECT id, title, slug, summary, content_markdown, status, created_at, updated_at FROM blog_posts WHERE slug = ?",
            (slug,),
        )

    def search_calls_today(self, user_id: int) -> int:
        row = self._fetchone(
            "SELECT COUNT(*) AS c FROM api_usage WHERE user_id = ? AND substr(request_at, 1, 10) = ?",
            (user_id, datetime.now(timezone.utc).date().isoformat()),
        )
        return int(row["c"]) if row else 0

    def get_subscription(self, user_id: int):
        return self._fetchone(
            "SELECT user_id, plan, status, started_at, renewed_at FROM subscriptions WHERE user_id = ?",
            (user_id,),
        )

    def upsert_subscription(self, user_id: int, plan: str, status: str = "active") -> None:
        now = _utc_now_iso()
        with self._connect() as conn:
            if self._backend == "sqlite":
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
                return
            conn.execute(
                """
                INSERT INTO subscriptions (user_id, plan, status, started_at, renewed_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT(user_id) DO UPDATE SET
                    plan = EXCLUDED.plan,
                    status = EXCLUDED.status,
                    renewed_at = EXCLUDED.renewed_at
                """,
                (user_id, plan, status, now, now),
            )
            conn.commit()

    def create_payment_record(
        self,
        user_id: int,
        order_id: str,
        amount_paise: int,
        currency: str,
        plan: str,
        status: str = "created",
    ) -> int:
        now = _utc_now_iso()
        with self._connect() as conn:
            if self._backend == "sqlite":
                conn.execute(
                    """
                    INSERT INTO payments (user_id, order_id, amount_paise, currency, plan, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(order_id) DO NOTHING
                    """,
                    (user_id, order_id, amount_paise, currency, plan, status, now),
                )
                row = conn.execute("SELECT id FROM payments WHERE order_id = ?", (order_id,)).fetchone()
                return int(row["id"])
            cur = conn.execute(
                """
                INSERT INTO payments (user_id, order_id, amount_paise, currency, plan, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(order_id) DO UPDATE SET order_id = EXCLUDED.order_id
                RETURNING id
                """,
                (user_id, order_id, amount_paise, currency, plan, status, now),
            )
            new_id = int(cur.fetchone()["id"])
            conn.commit()
            return new_id

    def complete_payment(
        self,
        order_id: str,
        payment_id: str,
        signature: str,
        webhook_event_id: str | None = None,
    ) -> bool:
        now = _utc_now_iso()
        with self._connect() as conn:
            if self._backend == "sqlite":
                existing = conn.execute(
                    "SELECT status, payment_id FROM payments WHERE order_id = ?",
                    (order_id,),
                ).fetchone()
                if existing is None:
                    return False
                if existing["status"] == "captured":
                    return True
                conn.execute(
                    """
                    UPDATE payments
                    SET payment_id = ?, signature = ?, webhook_event_id = COALESCE(?, webhook_event_id),
                        status = 'captured', processed_at = ?
                    WHERE order_id = ?
                    """,
                    (payment_id, signature, webhook_event_id, now, order_id),
                )
                return True
            existing = conn.execute(
                "SELECT status, payment_id FROM payments WHERE order_id = %s",
                (order_id,),
            ).fetchone()
            if existing is None:
                conn.commit()
                return False
            if existing["status"] == "captured":
                conn.commit()
                return True
            conn.execute(
                """
                UPDATE payments
                SET payment_id = %s, signature = %s, webhook_event_id = COALESCE(%s, webhook_event_id),
                    status = 'captured', processed_at = %s
                WHERE order_id = %s
                """,
                (payment_id, signature, webhook_event_id, now, order_id),
            )
            conn.commit()
            return True

    def get_payment_by_order_id(self, order_id: str):
        return self._fetchone(
            "SELECT id, user_id, order_id, payment_id, signature, amount_paise, currency, plan, status, created_at FROM payments WHERE order_id = ?",
            (order_id,),
        )

    def list_payments(self, user_id: int, limit: int = 20) -> list:
        return self._fetchall(
            "SELECT order_id, payment_id, amount_paise, currency, plan, status, created_at FROM payments WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        )
