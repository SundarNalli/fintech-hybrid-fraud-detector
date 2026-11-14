# Hybrid Fraud Detector

A fast rules path decides the obvious payouts. A slow, checked AI path looks at the gray ones. **The AI advises. A plain program decides.**

> **Practice scenario.** The company in the brief (ThalentQore), its merchants and every figure are fictional. All data in this repo is synthetic. Nothing here describes a real business, and nothing private belongs in this repo.

## Status

**Phases 0 to 7 are built and wired together:** the synthetic data, the rules-only hot path, the payout service with its hold lifecycle and append-only ledger, the agent, the verifier and policy wrapper, and an evaluation harness. **No real model has been run yet.** The evaluation so far used a scripted stand-in, so it checks the pipeline and the guard, not how good a model is. Read [docs/results-memo.md](docs/results-memo.md) first. A read-only ops screen is built (`make serve`, then open http://127.0.0.1:8000/). See [docs/problem-restated.md](docs/problem-restated.md) for the problem in one page.

Try the rules-only replay (Python 3.12, `pip install -e ".[dev]"`):

```bash
python -m hybrid_fraud.sim.replay
python -m pytest -q
```

## How it will work

```
payout event --> HOT PATH (rules, target p99 < 150 ms)
                   APPROVE | BLOCK | FAST_HUMAN_LANE | PENDING_REVIEW
                                        | gray cases only
                                        v
                 AGENT (read-only tools, max 4 calls, budget capped)
                                        v
                 VERIFIER (every claim must trace to a real record)
                                        v
                 POLICY WRAPPER (deterministic, asymmetric, final say)
                                        v
                 decision --> append-only audit ledger --> ops UI
```

## Where things live

| Folder | What it holds |
|---|---|
| `src/hybrid_fraud/core/` | Schemas, reason codes, config loading |
| `src/hybrid_fraud/hot_path/` | Features, hard rules, scoring, routing |
| `src/hybrid_fraud/agent/` | Tools, the agent loop, budget meter, LLM providers |
| `src/hybrid_fraud/guard/` | Verifier and policy wrapper |
| `src/hybrid_fraud/audit/` | Append-only ledger, evidence traces |
| `src/hybrid_fraud/store/` | SQLite: loading, lookups, the agent's read-only view |
| `src/hybrid_fraud/service/` | The payout endpoint, idempotency, hold lifecycle and reaper |
| `src/hybrid_fraud/sim/` | Synthetic data generator and scenario fixtures |
| `src/hybrid_fraud/eval/` | Evaluation harness and KPI report |
| `config/` | Thresholds, every value tagged with where it came from |
| `docs/` | Decision log, assumptions register, KPI definitions |

Each folder has its own short README.

## For a client conversation

[Demo script](docs/client/demo-script.md), [pilot proposal](docs/client/pilot-proposal.md), [risk register](docs/client/risk-register.md) and [what this prototype does not prove](docs/client/what-this-does-not-prove.md).

## Reading order

1. [docs/problem-restated.md](docs/problem-restated.md)
2. [docs/kpi-definitions.md](docs/kpi-definitions.md)
3. [docs/assumptions-register.md](docs/assumptions-register.md)
4. [docs/decision-log.md](docs/decision-log.md)

## Running it

`make demo` starts the service with no API key (replay mode: held payouts fail safe to the human queue; no model runs). Live mode will need your own key, set in an untracked `.env` (see `.env.example`).

## Keys and secrets

No key ever goes in the repo or the UI. `.env` is git-ignored, and a pre-commit hook scans for secrets (`pre-commit install`, then it runs on every commit).

## License

[MIT](LICENSE). Everything here is synthetic and a practice scenario; it is not production fraud software.
