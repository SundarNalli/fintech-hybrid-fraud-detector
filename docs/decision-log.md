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

## D-015 The service: one lock, one transaction per decision (14 Nov 2026)
**Decision:** `PayoutService.submit` takes an `Idempotency-Key`. A repeated key with the same body returns the stored decision and writes nothing; a different body, or a reused `payout_id`, is a 409. A new payout is decided and its payout row and ledger rows commit in one SQLite transaction, so they exist together or not at all. One lock serialises writers.
**Why:** Simple to explain and to test. The cost is that throughput is bounded by one writer; the latency numbers include that.
**Status:** decided.

## D-016 Holds are escalated by a reaper that survives restarts (14 Nov 2026)
**Decision:** A held payout (PENDING_REVIEW) stores a deadline (10 s, INVENTED, A-20). `reap()` moves any hold past its deadline to ESCALATED, reason `HOLD_DEADLINE_EXPIRED`, decided by "timeout". It runs every second while the API is up and once on every startup. Hold state and the ledger live in SQLite; velocity counters are rebuilt from stored payouts on startup.
**Why:** A crash must never leave a payout waiting forever.
**Status:** decided. Refines D-003: the counters are in memory, and the durable record is the payouts table, not a separate write-behind.

## D-017 The ledger is tamper-evident, not tamper-proof (14 Nov 2026)
**Decision:** Triggers reject UPDATE and DELETE; each row hashes its content with the previous row's hash. Forward-only state moves are checked where the rows are written.
**Why:** Cheap, testable and easy to explain. A hash chain cannot detect rows cut off the end; copying the head hash elsewhere would, in a real deployment.
**Status:** decided.

## D-018 The agent's repository is bound to a moment (14 Nov 2026)
**Decision:** `SQLiteReadOnlyRepository(db, as_of)` opens SQLite with `mode=ro` and only shows what was known at `as_of`. The graph links merchants through shared devices and through payees created within the last 168 hours (older payees are shared vendors such as a cloud provider, and would link everyone). `graph_clean` means no mule-flagged neighbours and fewer than 3 merchants on a device.
**Status:** decided. The 168 hours and the `graph_clean` definition are INVENTED (A-35).

## D-019 The gray-zone path is wired into the service (14 Nov 2026)
**Decision:** `GrayZoneProcessor` takes a held payout through agent, verifier and policy wrapper, then calls `service.resolve`. Over HTTP it runs as a background task after the response, so the hot path never waits for a model. Any failure at any step (provider error, timeout, malformed output, rejected verification) ends in ESCALATED. If the hold expired while the agent was thinking, the reaper's decision stands and is not overwritten.
**Status:** decided.

## D-020 Hard-fact field names must be the repository's field names (14 Nov 2026)
**Decision:** The guard's hard facts use `has_2fa_ticket_48h`, `has_credential_ticket_48h`, `on_mule_list` and `mule_flagged_neighbors`. A test checks every hard-fact field against what the real repository returns.
**Why:** The two sides had drifted apart, so no hard fact could ever fire on real evidence, and each side's own tests still passed. Tests that use hand-made records cannot catch this.
**Status:** decided and fixed.

## D-021 One fence function (14 Nov 2026)
**Decision:** The agent's prompt uses `guard.injection_hygiene.wrap_untrusted`, so the repo has one delimiter format, `<<<UNTRUSTED_DATA label>>>` to `<<<END_UNTRUSTED_DATA label>>>`.
**Status:** decided.

## D-022 The evaluation runs a scripted stand-in until a real model is run (14 Nov 2026)
**Decision:** `eval/run.py` supports `scripted`, `replay` and `live` providers. The scripted one is a fixed rule, not a model, and every report that uses it says so. A live run needs `--confirm`, model prices (so spend can be metered) and a dollar cap.
**Why:** The pipeline and the guard can be tested for free and repeatably. Real-model numbers cost money and are the user's call.
**Status:** decided. Real-model results are still to come.

## D-023 The ops screen is one plain HTML page, read-only
**Decision:** The ops UI is a single static page (`service/static/ops.html`, vanilla JavaScript, no build step) served by the same FastAPI app at `/`. It lists payouts, shows why each was decided (rule reasons, evidence trace, the ledger timeline) and plays demo cases through the real service. It has no approve, block or release button. Merchant-typed text (memo, payee name) is inserted with `textContent` only and labelled untrusted.
**Why:** The plan said React + Vite; that adds a Node toolchain and a build the reader must understand before they can follow the story. One file they can read top to bottom fits the goal that the code is easy to explain. A human decision button needs a login and an audit identity first; building it without them would be a hole in the ledger's story.
**Not built:** a threshold sandbox, a KPI dashboard (the numbers live in `docs/eval-results.md`), a tool-call timeline (tool calls are not stored in the ledger yet) and a live stream push (the page polls every 3 s).
**Demo cases:** one story per fraud kind, chosen by a rules-only replay so each shows the system acting, plus one miss (fraud the rules approved) and one ordinary payout. Playing a case twice is a replay by idempotency key.
**Status:** decided.

## O-002 Which false-positive definition the client manages to
Held payouts counted or not (KPI 3 and 4). **Open until a real client answers.**

## O-003 Default model
Chosen by measurement in Phase 5: the cheapest tool-capable model whose verdicts hold, whose output the verifier accepts, and that repeats across 5 runs. **Open until Phase 5.**

## D-024 License: MIT
**Decision:** MIT, copyright 2026 Sundar Nalli, chosen by the owner before publishing.
**Why:** The repo is a public learning project; MIT is short and permissive. It covers the code and the synthetic data. It is not a warranty that anything here suits real payments (see `docs/client/what-this-does-not-prove.md`).
**Status:** decided. Closes the former open item O-004.
