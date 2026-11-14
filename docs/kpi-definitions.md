# KPI definitions

Every number in the brief gets one written definition: numerator, denominator, window, source. Where the brief is silent, the gap is listed under **Open**.

"Paid out" means the payout was approved and money left. Blocked or held payouts lose nothing.

| # | KPI | Brief | Definition | Source in prototype |
|---|---|---|---|---|
| 1 | Fraud loss (bps) | 48 now, 15 or less target | Dollars of confirmed fraud among paid-out payouts, as known 120 days after the payout, divided by dollars paid out, times 10,000. Grouped by payout month. | Labels table |
| 2 | Fraud catch rate | not in brief | Share of fraudulent payouts (by label) not paid out. Reported twice: **auto-caught** (final state BLOCKED) and **caught or held** (also counts payouts waiting in the human queue, an upper bound). | Eval run |
| 3 | False-block rate, by payout | 14% now, 3.5% target (brief says "false positives") | Legitimate payouts ending BLOCKED, divided by all legitimate payouts. | Eval run |
| 4 | False-hold rate, by payout | not in brief | Legitimate payouts ending ESCALATED or FAST_HUMAN_LANE, divided by all legitimate payouts. | Eval run |
| 5 | False positives, by merchant | not in brief | Merchants with at least one legitimate payout blocked or held in the period, divided by all merchants. Also reported for the top 200 merchants alone. | Eval run |
| 6 | Auto-resolution rate | 82% now, 92% target | Payouts reaching APPROVED or BLOCKED with no human step, divided by all payouts. The human-queue share is 100% minus this, so it is reported once, not as a second target. | Eval run |
| 7 | Hot-path latency | p99 under 150 ms | Time inside the payout endpoint for hot-path decisions, p50, p95 and p99. In-process, no network, so it understates a real deployment. | Latency harness |
| 8 | Gray-zone latency | p95 under 6 s, hard limit 8 s | Time from PENDING_REVIEW to a final decision. A case hitting the limit becomes ESCALATED. | Orchestrator timing |
| 9 | Cost per gray-zone case | $0.03 cap | Dollars from the provider's reported token usage, per case. Also reported: total cost divided by extra frauds caught beyond rules. | Budget meter |
| 10 | Ungrounded-claim rate | "0% hallucination" | Share of agent claims failing the verifier (cited record absent, or the claim is false against the record). Reported **before** the verifier (how often the model does it) and **after** (decisions built on one, which is zero by construction). | Verifier |
| 11 | Wrong-conclusion rate | not in brief | Gray-zone cases where the recommendation disagrees with the label: APPROVE on fraud, or BLOCK on legitimate. ESCALATE_HUMAN counts as an abstention, reported separately. | Against labels |
| 12 | Repeatability | not in brief | Same case run 5 times: share of cases with the same verdict every time. | Eval run |

## Maturity window

Fraud loss is only final after about 120 days. The brief's 48 bps is a floor: what was found, not what happened. In the prototype the labels table holds full truth, so loss is known immediately. Say so wherever a loss figure appears.

## Wording of the "zero hallucination" promise

The promise is **zero ungrounded claims**: every claim traces to a record we can show an auditor. It is not "the AI is never wrong". Wrong conclusions are reported separately as KPI 11. Compliance would need to sign off the narrower wording.

## Open

- **KPI 3 and 4:** the brief's 14% and 3.5% do not say whether a held payout counts as a false positive. Both are reported until the client picks.
- **Baseline for KPI 6:** the brief gives 82% and 18% for one number. Confirm which one the client manages to.
- **Time zone and window edges** for velocity counters are set in Phase 1 (decision log O-001).
