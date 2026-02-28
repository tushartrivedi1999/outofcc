from __future__ import annotations

import random
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.console import SearchConsoleService
from app.user_store import UserStore


def run() -> int:
    random.seed(42)
    svc = SearchConsoleService()
    with tempfile.TemporaryDirectory() as d:
        store = UserStore(f"{d}/monkey.db")
        uid = store.create_user("monkey", "admin")

        for i in range(150):
            token = svc.create_token()
            domain = f"site-{i}.example.com"
            site_id = store.create_site(uid, domain, token)
            if random.random() > 0.3:
                store.mark_site_verified(site_id, random.choice(["dns", "url-prefix"]))
                store.seed_site_metrics(site_id, svc.default_daily_metrics(random.randint(3, 20)))
            if random.random() > 0.5:
                store.add_site_issue(site_id, "Random issue", random.choice(["low", "medium", "high"]), "open", "Monkey-generated")

            if random.random() > 0.2:
                store.log_api_usage(uid, f"query {i}", random.randint(20, 1500), random.randint(0, 20))

        for i in range(20):
            did = store.create_dataset(uid, f"dataset-{i}", random.choice(["open-search", "commoncrawl"]), "query", random.randint(10, 30))
            rows = [{"content": f"row-{j}", "source_url": f"https://src/{j}"} for j in range(random.randint(1, 30))]
            store.add_dataset_rows(did, rows)

        for i in range(5):
            store.create_blog_post(uid, f"Post {i}", f"post-{i}", "summary", "content")

        assert len(store.list_sites(uid)) == 150
        assert len(store.list_datasets(uid)) == 20
        assert len(store.list_blog_posts()) == 5

    print("Monkey test completed: data invariants OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
