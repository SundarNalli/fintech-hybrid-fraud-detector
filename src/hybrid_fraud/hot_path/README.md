# hot_path

The fast, synchronous path. Fetch features, run hard rules, score, and route: APPROVE, BLOCK, FAST_HUMAN_LANE or PENDING_REVIEW. Every decision carries a reason code and an evidence trace built from real field values by templates, never by an LLM.

| File | What |
|---|---|
| `features.py` | `PayoutFeatures` (what is known at payout time) and the lookup protocol |
| `velocity.py` | Count and dollar counters, per merchant and per beneficiary. Window rules in D-011 |
| `gate0_rules.py` | Six narrow hard rules, each returning an evidence line |
| `scoring.py` | A score from named contributions, no fitted model |
| `router.py` | The exhaustive routing table (D-009) |

Target: p99 under 150 ms, measured in Phase 2.

*Built in Phase 1 (rules and routing) and Phase 2 (service, ledger, latency).*
