# Evaluation results

Run on 2026-11-14. Agent: **SCRIPTED STAND-IN (not a model), fault rate 0%**. 3 repeat(s). Population: 20,000 synthetic payouts (96 fraudulent). Held by the hot path: 82.

> **This run used a scripted stand-in, not a model.** It follows a fixed rule and reads the same tool output a model would. It checks that the pipeline and the guard work end to end, and it measures what the policy wrapper does to a sensible recommendation. It says nothing about how well a real model investigates. Column B below is the stand-in's score, not an AI result.

## 1. The whole population

A: every held payout goes to the human queue. B: held payouts go agent, verifier, policy wrapper. C: the old perfect-oracle ceiling. Brackets are 95% intervals.

| Measure | A rules only | B rules + agent | C perfect oracle |
|---|---|---|---|
| Fraud blocked | 34/96 = 35.4% (26.6 to 45.4) | 52/96 = 54.2% (44.2 to 63.8) | 74/96 = 77.1% (67.7 to 84.4) |
| Fraud held for humans | 40/96 = 41.7% (32.3 to 51.7) | 22/96 = 22.9% (15.6 to 32.3) | 0/96 = 0.0% (0.0 to 3.8) |
| Fraud approved (missed) | 22/96 = 22.9% (15.6 to 32.3) | 22/96 = 22.9% (15.6 to 32.3) | 22/96 = 22.9% (15.6 to 32.3) |
| Fraud caught or held | 74/96 = 77.1% (67.7 to 84.4) | 74/96 = 77.1% (67.7 to 84.4) | 74/96 = 77.1% (67.7 to 84.4) |
| Stolen dollars paid out | $121,486 | $121,486 | $121,486 |
| Loss on paid-out dollars (bps) | 4.9 | 4.9 | 4.9 |
| Legitimate blocked | 4/19904 = 0.02% (0.01 to 0.05) | 8/19904 = 0.04% (0.02 to 0.08) | 4/19904 = 0.02% (0.01 to 0.05) |
| Legitimate held for humans | 42/19904 = 0.21% (0.16 to 0.29) | 35/19904 = 0.18% (0.13 to 0.24) | 0/19904 = 0.00% (0.00 to 0.02) |
| Merchants hit by a false block or hold | 40/3956 = 1.01% (0.74 to 1.37) | 39/3956 = 0.99% (0.72 to 1.34) | 4/3956 = 0.10% (0.04 to 0.26) |
|   of which top-200 merchants | 0/200 = 0.00% (0.00 to 1.88) | 0/200 = 0.00% (0.00 to 1.88) | 0/200 = 0.00% (0.00 to 1.88) |
| Auto-resolved (no human) | 19918/20000 = 99.6% (99.5 to 99.7) | 19943/20000 = 99.7% (99.6 to 99.8) | 20000/20000 = 100.0% (100.0 to 100.0) |

Loss in bps is stolen dollars among paid-out dollars, times 10,000 (KPI 1). The brief's baseline is 48 and its target is 15 or less; the labels give full truth, so there is no 120-day maturity wait here.

**What the agent cannot reach.** The agent only sees payouts the rules hold. 22 of 96 fraud payouts (23%) were approved on the hot path, so they never reach it, and even the perfect oracle leaves them untouched. Closing that gap is a job for the rules, not the agent.

**Rules alone already beat the loss target in this synthetic world** (4.9 bps against 15). The generator's missed fraud is small-dollar, because the large fraud payouts are the ones the rules catch. So this world cannot show that the agent is needed to hit the target, and it should not be read as showing that it is not.

## 2. The held payouts only

82 cases: 40 fraudulent, 42 legitimate.

| Measure | B rules + agent | C perfect oracle |
|---|---|---|
| Approved | 3/82 = 3.7% (1.3 to 10.2) | 42/82 = 51.2% (40.6 to 61.7) |
| Blocked | 22/82 = 26.8% (18.4 to 37.3) | 40/82 = 48.8% (38.3 to 59.4) |
| Sent to humans | 57/82 = 69.5% (58.9 to 78.4) | 0/82 = 0.0% (0.0 to 4.5) |
| Fraud blocked | 18/40 = 45.0% (30.7 to 60.2) | 40/40 = 100.0% (91.2 to 100.0) |
| Legitimate approved | 3/42 = 7.1% (2.5 to 19.0) | 42/42 = 100.0% (91.6 to 100.0) |
| Wrong, of those it decided | 4/25 = 16.0% (6.4 to 34.7) | 0/82 = 0.0% (0.0 to 4.5) |
| Wrong, of all held | 4/82 = 4.9% (1.9 to 11.9) | 0/82 = 0.0% (0.0 to 4.5) |

A wrong call is an approved fraud or a blocked legitimate payout. Sending a case to a human is never counted wrong, which is why the rate is shown both ways.

## 3. What the policy wrapper did to the agent's recommendations

| Agent recommended | Final state | Cases |
|---|---|---|
| APPROVE | APPROVED | 3 |
| APPROVE | ESCALATED | 30 |
| BLOCK | BLOCKED | 22 |
| ESCALATE_HUMAN | ESCALATED | 27 |

Guard reasons behind downgrades and escalations:

- `GUARD_APPROVE_OVER_CAP`: 30

The AI-approval cap is $1,000 (an invented placeholder, A-19). Every `GUARD_APPROVE_OVER_CAP` above is a case where the agent recommended approval and the cap sent it to a human instead. Whether those approvals were right is not known from this table.

## 4. Agent mechanics

| Measure | Value |
|---|---|
| Tool calls per case (mean) | 4.0 |
| Latency per case, p50 / p95 (seconds) | 0.016 / 0.031 |
| Cost per case (mean) | $0 (no priced model in this run) |
| Cost per extra fraud caught | n/a |
| Claims made | 121 |
| Ungrounded claims, before the verifier | 0/121 = 0.0% (0.0 to 3.1) |
| Cases the verifier rejected | 0/82 = 0.0% (0.0 to 4.5) |
| Decisions built on an ungrounded claim | 0 (must be 0) |

Latency and cost here are those of a local script, so they say nothing about a real model. The ungrounded-claim rate is the injected fault rate, not a model's behaviour.

## 5. Repeatability

100.0% of held cases reached the same final state in all 3 runs. This is trivially 100% for a deterministic script and is not evidence about a model.

## 6. Reading these results

- **Synthetic data.** Every effect depends on how the generator was built. Legitimate friction here is far below the earlier test's 1.87% false blocks (A-34), so a real business would look different.
- **Small sample.** 82 held cases and 96 fraud payouts make the intervals wide. A result of zero failures in 80 cases only shows the true rate is below about 4%.
- **The cases are the generator's own gray zone**, not analyst-labelled ones. Templated text is cleaner than real attacker text, and the labels came from the same code that made the data, so a model could look better here than on real cases.
- **Not run:** a real model, the tools-versus-no-tools comparison, comparing model sizes, and the cost-ratio threshold sliders. All need a live model.
