#!/usr/bin/env python3
"""Quick benchmark for balatrobot steps/second."""

import json
import time
import urllib.request
from collections import deque

PORT = 12346
URL = f"http://localhost:{PORT}"


def rpc(method, params=None, req_id=1):
    body = json.dumps({"jsonrpc": "2.0", "method": method, "params": params or {}, "id": req_id}).encode()
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def bench(label, fn, n=100):
    times = deque()
    for i in range(n):
        t = time.perf_counter()
        fn(i)
        times.append(time.perf_counter() - t)
    avg_ms = (sum(times) / len(times)) * 1000
    sps = 1 / (sum(times) / len(times))
    print(f"{label:30s}  avg {avg_ms:6.1f}ms  {sps:6.1f} steps/sec")


print("=== balatrobot benchmark ===\n")

# Baseline: raw RPC overhead
bench("health (baseline rpc)", lambda i: rpc("health"))
bench("gamestate (read-only)", lambda i: rpc("gamestate"))

# Game action benchmark — requires a run already in progress
def play_step(i):
    gs = rpc("gamestate")["result"]
    state = gs.get("state")
    if state == "SELECTING_HAND":
        cards = [c["id"] for c in gs["hand"]["cards"][:5]]
        rpc("play", {"cards": cards})
    elif state == "SHOP":
        rpc("next_round", {})
    elif state == "BLIND_SELECT":
        rpc("select", {})

bench("play hand (full step)", play_step, n=50)

print("\nDone. Multiply steps/sec by number of instances for total throughput.")
