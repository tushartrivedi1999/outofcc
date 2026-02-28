from __future__ import annotations

from collections import Counter


def weighted_round_robin(backends: list[tuple[str, int]], requests: int) -> Counter:
    sequence: list[str] = []
    for name, weight in backends:
        sequence.extend([name] * weight)
    counts: Counter = Counter()
    for i in range(requests):
        target = sequence[i % len(sequence)]
        counts[target] += 1
    return counts


def run() -> int:
    backends = [("searx-a", 5), ("searx-b", 3), ("searx-c", 2)]
    counts = weighted_round_robin(backends, 10_000)
    print("Distribution:", dict(counts))

    total = sum(counts.values())
    ratios = {k: v / total for k, v in counts.items()}

    expected = {"searx-a": 0.5, "searx-b": 0.3, "searx-c": 0.2}
    for key, exp in expected.items():
        if abs(ratios[key] - exp) > 0.02:
            print("Load-balance drift too high", key, ratios[key], exp)
            return 1

    print("Load-balance simulation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
