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

## O-001 Velocity window semantics
Inclusive or exclusive edges, clock source, time zone. **Open until Phase 1.**

## O-002 Which false-positive definition the client manages to
Held payouts counted or not (KPI 3 and 4). **Open until a real client answers.**

## O-003 Default model
Chosen by measurement in Phase 5: the cheapest tool-capable model whose verdicts hold, whose output the verifier accepts, and that repeats across 5 runs. **Open until Phase 5.**

## O-004 License
The repo is meant to be public. A license must be chosen before it is. **Open: owner's decision.**
