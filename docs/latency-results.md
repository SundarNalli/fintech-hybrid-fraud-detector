# Hot-path latency results

Run: `python -m hybrid_fraud.eval.latency` (50,000 events). One run, 14 Nov 2026, on the development laptop (Windows 11, Python 3.12, SQLite in WAL mode with `synchronous=NORMAL`).

| Metric | Result | Target (brief) |
|---|---|---|
| p50 | 0.18 ms | |
| p95 | 0.26 ms | |
| **p99** | **4.19 ms** | under 150 ms |
| mean | 0.29 ms | |
| max | 181 ms | |

The ledger hash chain verified after all 50,000 events.

## What this measures

One call to `PayoutService.submit`, in-process: feature lookups from SQLite, the rules, and the transaction that stores the decision and its ledger rows.

## What it does not measure

- **Network and HTTP.** No request parsing, no TLS, no round trip.
- **A separate feature store.** A real deployment reads velocity from something like Redis over the network and merchant data from another service.
- **Concurrent callers.** One caller, so no queueing behind the single writer lock.
- **A production database.** SQLite on one machine, and `synchronous=NORMAL` does not flush to disk on every commit, which a production system would not accept for money movement.
- **Realistic data.** The synthetic set has 20,000 payouts, replayed 2.5 times with shifted dates to reach 50,000.

So read these as a floor. The target is met by a wide margin, but this run cannot say what a real deployment would see.

## Notes

- **The maximum (181 ms) is a single outlier**, well above the p99. It is likely a database checkpoint or a garbage-collection pause, but I did not investigate. One run is not enough to say how often it happens.
- Numbers vary between runs. Re-run before quoting them.
