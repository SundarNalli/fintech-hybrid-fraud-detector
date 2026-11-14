# eval

The evaluation. It drives the real service code over the synthetic payouts and reports the KPIs in `docs/kpi-definitions.md` with 95% intervals, for three systems side by side: rules only, rules plus agent, and the earlier proof of concept's perfect-oracle ceiling.

| File | What |
|---|---|
| `run.py` | The runner. `--provider scripted`, `replay` or `live`; repeats; spend caps |
| `metrics.py` | The KPI maths and Wilson intervals. Pure functions, tested by hand |
| `report.py` | Turns a result into the markdown tables in `docs/` |
| `scripted_investigator.py` | A fixed-rule stand-in for the model. **Not a model**; every report that uses it says so |
| `latency.py` | The hot-path latency harness (Phase 2) |

```bash
python -m hybrid_fraud.eval.run --provider scripted --repeats 3 --out docs/eval-results.md
python -m hybrid_fraud.eval.run --provider scripted --fault-rate 0.1     # make 10% of cases deliberately wrong
python -m hybrid_fraud.eval.run --provider live --max-cases 20           # shows the worst-case cost, sends nothing
```

A live run needs your own key in `.env`, both `LLM_*_USD_PER_MTOK` prices, `--confirm`, and stops at its dollar cap. Read [docs/results-memo.md](../../../docs/results-memo.md) before quoting any number.

*Built in Phase 5.*
