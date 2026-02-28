from __future__ import annotations

import argparse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from statistics import mean
from urllib import error, request


@dataclass
class ProbeResult:
    ok: bool
    status: int
    latency_ms: float
    distorted: bool
    detail: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load test for /v1/search endpoint")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--api-key", default="replace-with-real-api-key")
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--requests", type=int, default=500, help="Total request count")
    parser.add_argument("--timeout", type=float, default=15.0)
    return parser.parse_args()


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, int(round((p / 100.0) * (len(ordered) - 1)))))
    return ordered[idx]


def is_distorted(payload: dict) -> bool:
    if not isinstance(payload, dict):
        return True
    required = {"query", "took_ms", "cached", "results", "generated_at"}
    if not required.issubset(payload.keys()):
        return True
    if not isinstance(payload.get("results"), list):
        return True
    return False


def request_once(base_url: str, api_key: str, timeout: float) -> ProbeResult:
    body = json.dumps({"q": "python fastapi", "num_results": 5, "language": "en"}).encode("utf-8")
    req = request.Request(
        f"{base_url.rstrip('/')}/v1/search",
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    started = time.perf_counter()
    try:
        with request.urlopen(req, timeout=timeout) as res:
            raw = res.read().decode("utf-8")
            latency_ms = (time.perf_counter() - started) * 1000
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                return ProbeResult(False, res.status, latency_ms, True, "non-json response")
            distorted = is_distorted(payload)
            return ProbeResult(res.status == 200 and not distorted, res.status, latency_ms, distorted, "")
    except error.HTTPError as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        return ProbeResult(False, int(exc.code), latency_ms, False, f"http error {exc.code}")
    except Exception as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        return ProbeResult(False, 0, latency_ms, False, f"transport error: {exc}")


def run() -> int:
    args = parse_args()

    warmup = request_once(args.base_url, args.api_key, args.timeout)
    if warmup.status == 0:
        print(f"Unable to reach server: {warmup.detail}")
        return 2

    latencies: list[float] = []
    distorted = 0
    success = 0
    failures = 0
    by_status: dict[int, int] = {}
    lock = threading.Lock()

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [executor.submit(request_once, args.base_url, args.api_key, args.timeout) for _ in range(args.requests)]
        for future in futures:
            item = future.result()
            with lock:
                by_status[item.status] = by_status.get(item.status, 0) + 1
                latencies.append(item.latency_ms)
                distorted += 1 if item.distorted else 0
                if item.ok:
                    success += 1
                else:
                    failures += 1

    duration = time.perf_counter() - started
    rps = args.requests / duration if duration else 0.0

    print(f"Total requests: {args.requests}")
    print(f"Success: {success}")
    print(f"Failures: {failures}")
    print(f"Distorted responses: {distorted}")
    print(f"Status distribution: {dict(sorted(by_status.items()))}")
    print(f"Duration: {duration:.2f}s")
    print(f"Throughput: {rps:.2f} req/s")
    print(f"Average latency: {mean(latencies):.2f} ms" if latencies else "Average latency: 0.00 ms")
    print(f"P50 latency: {percentile(latencies, 50):.2f} ms")
    print(f"P95 latency: {percentile(latencies, 95):.2f} ms")
    print(f"P99 latency: {percentile(latencies, 99):.2f} ms")

    return 0 if failures == 0 and distorted == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run())
