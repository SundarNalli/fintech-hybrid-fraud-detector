# Decision log

One entry per decision: what, why, status. Newest last. "Open" items are decisions waiting on a later phase.

## D-001 Python only (14 Nov 2026)
**Decision:** The whole repo is Python 3.12. A Rust port of the hot path is an optional stretch after Phase 7.
**Why:** This is a learning exercise that will be published. A reader should follow the code in one sitting, and one language means one copy of the rules code.
**Status:** decided.

## D-002 SQLite for storage (14 Nov 2026)
**Decision:** SQLite in WAL mode, standard-library `sqlite3`, behind a small repository interface.
**Why:** Simple to run and to explain. Swap to Postgres later if needed.
**Status:** decided.

## D-003 In-process velocity counters, not Redis (14 Nov 2026)
**Decision:** Counters live in process with a SQLite write-behind.
**Why:** The brief names Redis. This is a stand-in, and the notes must say so.
**Status:** decided.

## D-004 No agent framework, no ORM (14 Nov 2026)
**Decision:** The tool-call loop is plain code over HTTP, about 60 lines.
**Why:** Explainability. Every moving part is readable in the repo.
**Status:** decided.

## D-005 Replay by default, no key in the UI (14 Nov 2026)
**Decision:** With no API key, the agent serves recorded responses. Keys come only from the environment or an untracked `.env`. The UI never takes a key.
**Why:** A clone of the public repo runs with no key and no spend. Pasting secrets into a web form would be a bad habit to model.
**Status:** decided.

## D-006 Public repo, synthetic data only (14 Nov 2026)
**Decision:** Everything is generated and labelled `synthetic: true`. No private data or text from other projects.
**Status:** decided.

## D-007 Asymmetric policy wrapper (14 Nov 2026)
**Decision:** APPROVE needs at least two grounded positive claims resting on fields the merchant cannot write, a clean graph, no 2FA or credential ticket, and an amount under the AI-approval cap. BLOCK needs one grounded hard signal. Anything weaker downgrades to ESCALATE_HUMAN.
**Why:** An approved payout cannot be undone.
**Status:** decided. Cap value is INVENTED (A-19).

## D-008 Claims are typed predicates (14 Nov 2026)
**Decision:** `{field, op, value, evidence_id}`, evaluated by the verifier against the record.
**Why:** Free text plus a real ID proves a record exists, not that it supports the claim.
**Status:** decided.

## D-009 Routing is exhaustive, first match wins (14 Nov 2026)
**Decision:** Gate 0 hit goes to BLOCK, or FAST_HUMAN_LANE for a top-200 merchant. Then Gate 1: 0.82 or above goes to BLOCK or the fast lane; 0.45 to 0.82 goes to PENDING_REVIEW; below 0.45 with a novel anomaly over $2,500 goes to PENDING_REVIEW; otherwise APPROVE with the novel flag logged.
**Status:** decided. Thresholds live in `config/thresholds.toml`.

## D-010 Repo layout (14 Nov 2026)
**Decision:** One folder per diagram box under `src/hybrid_fraud/`, each with a short README. Dependencies are added phase by phase.
**Status:** decided.

## D-011 Velocity window semantics (14 Nov 2026)
**Decision:** A window of length W ending at `now` covers events with `now - W < ts <= now`: lower edge exclusive, upper inclusive. All times are timezone-aware UTC. The payout being scored counts in its own window ("the totals if we approve it"). Events are recorded after scoring, in time order. Windows: 1 hour and 24 hours, in count and dollars, per merchant and per beneficiary across merchants.
**Why:** One written rule so counters, tests and replay agree. Resolves O-001.
**Status:** decided. Tests in `tests/hot_path/test_velocity.py`.

## D-012 "Novel anomaly" means a payee the platform has not seen this week (14 Nov 2026)
**Decision:** A payout is novel when this merchant has never paid the payee before and nobody on the platform first paid them within the last 168 hours. A low-score payout that is novel and over $2,500 is held; under $2,500 it is approved with a logged flag.
**Why:** The brief does not define it. A looser definition (any first payment to a payee) would hold a large share of legitimate traffic.
**Status:** decided, INVENTED definition (A-27). Revisit in Phase 5.

## D-013 Four scenarios defined from the project notes (14 Nov 2026)
**Decision:** The client brief is not in this repo, so the four scenarios are defined from the examples in the notes: hard-rule block, clear approve, gray and really fraud, gray and legitimate. See `sim/scenarios.py`.
**Status:** decided, open to correction (A-26). If the real brief names different scenarios, replace the fixtures.

## D-014 The generator is one world with four fraud shapes (14 Nov 2026)
**Decision:** Fraud is bust-out, takeover, mule ring and structuring, so it is not only young merchants (42 of 96 fraud payouts are on accounts 90+ days old). A `noise` setting (default 0.35) makes each fraud signal look innocent independently, and some legitimate payouts are large or odd. Device logins and payees carry timestamps, so the service only sees what it would have known at payout time.
**Why:** Fixes the earlier proof of concept's known artifacts. Results are properties of this generator, not of the world.
**Status:** decided.

## O-002 Which false-positive definition the client manages to
Held payouts counted or not (KPI 3 and 4). **Open until a real client answers.**

## O-003 Default model
Chosen by measurement in Phase 5: the cheapest tool-capable model whose verdicts hold, whose output the verifier accepts, and that repeats across 5 runs. **Open until Phase 5.**

## O-004 License
The repo is meant to be public. A license must be chosen before it is. **Open: owner's decision.**
