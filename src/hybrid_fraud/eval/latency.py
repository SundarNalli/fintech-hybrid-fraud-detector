"""Hot-path latency harness.

    python -m hybrid_fraud.eval.latency [events]       # default 50,000

Replays synthetic payouts through `PayoutService.submit` and reports p50, p95
and p99 of the time each call takes.

What this measures: the service call in-process, including the feature lookups
and the SQLite transaction that stores the decision and its ledger rows.
What it does NOT measure: network, HTTP parsing, a separate feature store,
queueing under many callers, or a production database. A real deployment adds
all of those, so read these numbers as a floor.

The dataset has 20,000 payouts. To reach 50,000 events it is replayed with new
ids and timestamps shifted by 30 days per round, so velocity windows behave.
"""

from __future__ import annotations

import statistics
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path

from hybrid_fraud.core.config import load_thresholds
from hybrid_fraud.service.payout_service import PayoutService
from hybrid_fraud.sim.dataset_io import read_dataset
from hybrid_fraud.store.db import connect, load_world


def percentile(sorted_ms: list[float], p: float) -> float:
    return sorted_ms[min(len(sorted_ms) - 1, int(len(sorted_ms) * p))]


def run(events: int = 50_000) -> dict:
    ds, t = read_dataset(), load_thresholds()
    with tempfile.TemporaryDirectory() as tmp:
        conn = connect(Path(tmp) / "latency.db")
        load_world(conn, ds)
        service = PayoutService(conn, t)
        times: list[float] = []
        n = len(ds.payouts)
        for i in range(events):
            rnd, p = divmod(i, n)
            base = ds.payouts[p]
            payout = base.model_copy(update={
                "payout_id": f"{base.payout_id}_r{rnd}",
                "created_at": base.created_at + timedelta(days=30 * rnd)})
            t0 = time.perf_counter()
            service.submit(payout, f"key_{payout.payout_id}")
            times.append((time.perf_counter() - t0) * 1000)
        ok, _ = service.verify_ledger()
        conn.close()
    ms = sorted(times)
    return {
        "events": events,
        "p50_ms": round(percentile(ms, 0.50), 3), "p95_ms": round(percentile(ms, 0.95), 3),
        "p99_ms": round(percentile(ms, 0.99), 3), "max_ms": round(ms[-1], 3),
        "mean_ms": round(statistics.fmean(ms), 3),
        "target_p99_ms": t.latency_targets.hot_path_p99_ms,
        "ledger_chain_ok": ok,
    }


if __name__ == "__main__":
    result = run(int(sys.argv[1]) if len(sys.argv) > 1 else 50_000)
    for k, v in result.items():
        print(f"{k:16s} {v}")
    print("\nIn-process measurement: no network, no separate feature store. A floor, not a forecast.")
