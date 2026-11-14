# Pilot proposal: shadow, advisory, limited live

> Practice scenario. Targets come from the fictional brief; figures marked "proposal" are for the client to agree. Each stage needs its exit criteria met and a named person's sign-off before the next one starts.

## Stage 0: Ready to start (before any traffic)
- The client's real definitions agreed for KPI 3 and 4 (is a held payout a false positive?) and the KPI 6 baseline (82% or 18%).
- Real labels available: a way to learn which payouts were fraud, with the delay it really has.
- A model chosen by measurement (decision O-003) using the live evaluation on the client's own historical cases, with spend capped.
- The invented placeholders replaced or confirmed: the AI approval cap, the structuring limit, the score thresholds.
- A data-handling and provider review, because real payout data must not reach a model provider before it.

## Stage 1: Shadow mode (decisions logged, never enforced)
- **What runs:** the hot path and the agent score every payout. The client's existing system still decides. Our decision goes to the ledger only.
- **Duration (proposal):** at least 4 weeks, so every weekday and a month-end appear.
- **Exit criteria:**
  - Hot-path p99 under 150 ms on real traffic and the real network path.
  - Gray-zone p95 under 6 s; the share hitting the 8 s limit reported.
  - Decisions built on an ungrounded claim: 0. Ungrounded-claim rate before the verifier reported.
  - Where our decision and the existing one differ, a human reviewed a sample and we know who was right (agreement level to be set with the client).
  - Cost per gray-zone case at or under $0.03; cost per extra fraud caught reported.

## Stage 2: Advisory
- **What runs:** our decision and evidence are shown to the human reviewers. They decide. Nothing is automated.
- **Duration (proposal):** 4 weeks.
- **Exit criteria:** reviewers' agreement with our recommendation measured; review time per case measured; no logged case where the evidence shown was wrong or unreadable.

## Stage 3: Limited live
- **What runs:** automatic BLOCK for hard-rule hits and automatic APPROVE for clear cases, on a small share of merchants chosen with the client, with the AI approval cap kept low. Gray cases still reach a human unless policy allows otherwise.
- **Guardrails:** a kill switch that returns every payout to the old path; daily review of every automatic block a merchant disputes; a cap on the share of traffic.
- **Exit criteria:** false-block rate at or under the brief's 3.5% (on the agreed definition); no rise in fraud loss on the pilot share against a control share.

## The maturity window
Fraud labels arrive about 120 days late. A pilot can show catch rate and false blocks quickly, but **cannot confirm the 15 bps loss target until about four months after limited live starts**. Tell the client before the pilot, not after.

## Roles (to agree)
A client owner who can stop the pilot; a fraud-ops lead for reviews and sign-offs; compliance sign-off on the "zero ungrounded claims" wording (see [kpi-definitions.md](../kpi-definitions.md)).
