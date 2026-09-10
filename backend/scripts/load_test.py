"""
Load test the checkpointed session path (no LLM cost).

    python scripts/load_test.py --base https://<backend> --token <JWT> --users 10 --requests 200

Hits three endpoints that exercise the graph + checkpointer but never call
the model: GET /health, POST /session/start (runs `init` and checkpoints),
GET /session/{id} (reads a checkpoint). Reports p50/p95/max latency and
requests/second per endpoint as a Markdown table you can paste in a README.

Get a JWT from the browser: DevTools → Application → Local Storage → the
Supabase auth entry → access_token. It is short-lived; run soon after copying.
"""

import argparse
import asyncio
import math
import statistics
import time

import httpx


def pct(values, p):
    if not values:
        return float("nan")
    ordered = sorted(values)
    return ordered[max(1, math.ceil(p / 100 * len(ordered))) - 1]


async def worker(client, base, token, topic, n, results, session_ids):
    headers = {"Authorization": f"Bearer {token}"}
    for _ in range(n):
        t0 = time.perf_counter()
        r = await client.get(f"{base}/health")
        results["GET /health"].append(((time.perf_counter() - t0) * 1000, r.status_code))

        t0 = time.perf_counter()
        r = await client.post(f"{base}/api/v1/session/start", headers=headers,
                              json={"topic_id": topic["id"], "topic": topic["title"], "mastery": 0.3})
        results["POST /session/start"].append(((time.perf_counter() - t0) * 1000, r.status_code))
        if r.status_code == 200:
            sid = r.json()["session_id"]
            session_ids.append(sid)
            t0 = time.perf_counter()
            r = await client.get(f"{base}/api/v1/session/{sid}", headers=headers)
            results["GET /session/{id}"].append(((time.perf_counter() - t0) * 1000, r.status_code))


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="e.g. https://neolearn-api.onrender.com")
    ap.add_argument("--token", required=True, help="Supabase access token (JWT)")
    ap.add_argument("--users", type=int, default=10, help="concurrent workers")
    ap.add_argument("--requests", type=int, default=20, help="iterations per worker")
    ap.add_argument("--topic-id", default="load-test-topic")
    ap.add_argument("--topic", default="Load Test Topic")
    args = ap.parse_args()

    results = {"GET /health": [], "POST /session/start": [], "GET /session/{id}": []}
    session_ids: list[str] = []
    topic = {"id": args.topic_id, "title": args.topic}

    async with httpx.AsyncClient(timeout=60) as client:
        # warm the instance so a cold start doesn't pollute p95
        await client.get(f"{args.base}/health")
        started = time.perf_counter()
        await asyncio.gather(*(worker(client, args.base, args.token, topic, args.requests, results, session_ids)
                               for _ in range(args.users)))
        elapsed = time.perf_counter() - started

    total = sum(len(v) for v in results.values())
    print(f"\n{args.users} users × {args.requests} iterations, {total} requests in {elapsed:.1f}s "
          f"({total / elapsed:.1f} req/s overall), {len(session_ids)} sessions created\n")
    print("| Endpoint | n | p50 ms | p95 ms | max ms | errors |")
    print("|---|---|---|---|---|---|")
    for name, samples in results.items():
        lat = [s[0] for s in samples]
        errors = sum(1 for s in samples if s[1] >= 400)
        if lat:
            print(f"| `{name}` | {len(lat)} | {statistics.median(lat):.0f} | {pct(lat, 95):.0f} | {max(lat):.0f} | {errors} |")
    print("\nNote: sessions created by this run live in the checkpoints table; delete rows whose thread_id "
          "ends with these session ids if you want a clean table.")


if __name__ == "__main__":
    asyncio.run(main())
