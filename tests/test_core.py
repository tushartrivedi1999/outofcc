import hashlib
import tempfile
import threading
import time
import unittest
from pathlib import Path

from app.cache import TTLCache
from app.console import SearchConsoleService
from app.rate_limit import SlidingWindowRateLimiter
from app.security import generate_api_key, hash_password, verify_password
from app.session import SessionManager
from app.template_engine import TemplateEngine
from app.payments import RazorpayGateway
from app.user_store import UserStore
from scripts.load_test import is_distorted


class CoreTests(unittest.TestCase):
    def test_cache_ttl(self):
        cache = TTLCache[int]()
        cache.set("x", 7, ttl_s=1)
        self.assertEqual(cache.get("x"), 7)
        time.sleep(1.05)
        self.assertIsNone(cache.get("x"))

    def test_rate_limiter(self):
        limiter = SlidingWindowRateLimiter()
        self.assertTrue(limiter.allow("key", rpm=2))
        self.assertTrue(limiter.allow("key", rpm=2))
        self.assertFalse(limiter.allow("key", rpm=2))

    def test_rate_limiter_concurrent_safety(self):
        limiter = SlidingWindowRateLimiter()
        hits: list[bool] = []

        def task() -> None:
            hits.append(limiter.allow("concurrent", rpm=50))

        workers = [threading.Thread(target=task) for _ in range(200)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()

        self.assertLessEqual(sum(1 for ok in hits if ok), 50)

    def test_password_hashing(self):
        encoded = hash_password("admin")
        self.assertTrue(verify_password("admin", encoded))
        self.assertFalse(verify_password("wrong", encoded))

    def test_session_roundtrip(self):
        mgr = SessionManager("secret", max_age_s=10)
        token = mgr.create(user_id=42)
        self.assertEqual(mgr.verify(token), 42)

    def test_template_engine(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.html"
            p.write_text("hello ${name}", encoding="utf-8")
            engine = TemplateEngine(d)
            self.assertEqual(engine.render("x.html", {"name": "world"}), "hello world")

    def test_user_store_api_key(self):
        with tempfile.TemporaryDirectory() as d:
            db = str(Path(d) / "app.db")
            store = UserStore(db)
            user_id = store.create_user("u1", "admin")
            key = "osk_dummy"
            digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
            store.create_api_key(user_id, digest, key[:12], "free")
            row = store.find_api_key_by_hash(digest)
            self.assertIsNotNone(row)
            self.assertEqual(row["user_id"], user_id)

    def test_search_console_and_dataset_flow(self):
        with tempfile.TemporaryDirectory() as d:
            db = str(Path(d) / "app.db")
            store = UserStore(db)
            user_id = store.create_user("u1", "admin")
            svc = SearchConsoleService()

            token = svc.create_token()
            site_id = store.create_site(user_id, "example.com", token)
            payload = svc.build_verification_payload("example.com", token)
            self.assertIn(token, payload.dns_txt)

            store.mark_site_verified(site_id, "dns")
            rows = store.list_sites(user_id)
            self.assertEqual(int(rows[0]["verified"]), 1)

            metrics = svc.default_daily_metrics(7)
            store.seed_site_metrics(site_id, metrics)
            store.add_site_issue(site_id, "Broken canonical", "high", "open", "Canonical mismatch found")
            self.assertGreaterEqual(len(store.list_site_metrics(site_id)), 7)
            self.assertEqual(len(store.list_site_issues(site_id)), 1)

            store.log_api_usage(user_id, "python", 120, 8)
            self.assertEqual(len(store.list_recent_api_usage(user_id)), 1)

            dataset_id = store.create_dataset(user_id, "d1", "open-search", "python", 20)
            store.add_dataset_rows(dataset_id, [{"content": "x", "source_url": "https://a"}])
            self.assertEqual(len(store.list_datasets(user_id)), 1)
            self.assertEqual(len(store.dataset_rows(dataset_id)), 1)

            store.create_blog_post(user_id, "Release Notes", "release-notes", "sum", "content", "published")
            self.assertEqual(len(store.list_blog_posts()), 1)
            self.assertIsNotNone(store.find_blog_post_by_slug("release-notes"))

            self.assertGreaterEqual(store.search_calls_today(user_id), 1)
            store.upsert_subscription(user_id, "pro", "active")
            self.assertEqual(store.get_subscription(user_id)["plan"], "pro")
            pid = store.create_payment_record(user_id, "order_1", 99900, "INR", "pro")
            self.assertGreater(pid, 0)
            store.complete_payment("order_1", "pay_1", "sig")
            self.assertEqual(len(store.list_payments(user_id)), 1)

            svg = svc.build_svg_bars([1, 3, 2])
            self.assertIn("<svg", svg)

    def test_razorpay_signature_verifier(self):
        gateway = RazorpayGateway("key", "secret", "whsec")
        self.assertFalse(gateway.verify_signature("o", "p", "x"))
        self.assertFalse(gateway.verify_webhook_signature(b"{}", "bad"))

    def test_payment_completion_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            db = str(Path(d) / "app.db")
            store = UserStore(db)
            user_id = store.create_user("u2", "admin")
            store.create_payment_record(user_id, "order_2", 100, "INR", "pro")
            self.assertTrue(store.complete_payment("order_2", "pay_2", "sig_2"))
            self.assertTrue(store.complete_payment("order_2", "pay_2", "sig_2"))
            self.assertFalse(store.complete_payment("order_missing", "pay_x", "sig_x"))

    def test_generate_api_key_prefix(self):
        self.assertTrue(generate_api_key().startswith("osk_"))

    def test_distortion_detector(self):
        good = {
            "query": "x",
            "took_ms": 10,
            "cached": False,
            "results": [],
            "generated_at": "2020-01-01T00:00:00Z",
        }
        self.assertFalse(is_distorted(good))
        self.assertTrue(is_distorted({"query": "x"}))


if __name__ == "__main__":
    unittest.main()
