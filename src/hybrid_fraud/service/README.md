# service

The payout endpoint and the logic behind it.

| File | What |
|---|---|
| `payout_service.py` | `submit` (idempotent), `resolve` (apply a policy decision to a hold), `reap` (escalate expired holds), `recover` (rebuild after a restart) |
| `gray_zone.py` | `GrayZoneProcessor`: a held payout goes agent, verifier, policy wrapper, then `resolve`. Any failure ends in ESCALATED |
| `api.py` | FastAPI routes: `POST /api/payouts`, `GET /api/payouts/{id}`, `GET /api/payouts/{id}/ledger`, `GET /health` |
| `main.py` | Runs it locally and fills an empty database from the committed snapshot |

```bash
python -m hybrid_fraud.service.main      # http://127.0.0.1:8000/docs
python -m hybrid_fraud.eval.latency      # 50,000-event latency run
```

`POST /api/payouts` needs an `Idempotency-Key` header. A repeat returns the stored decision; the same key with a different body is a 409. Decisions D-015 to D-017 explain the rules.

A held payout is handed to the gray-zone processor after the response goes out, so the hot path never waits for a model. With no API key and no recordings the processor fails safe: the payout goes to the human queue. If the hold deadline passes while the agent is working, the reaper's escalation stands.

*Built in Phase 2.*
