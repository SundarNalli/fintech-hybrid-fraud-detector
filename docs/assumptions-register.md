# Assumptions register

Every number carries a tag:

- **BRIEF** stated in the client brief
- **DISCOVERY** from the simulated client call (confirm with a real client before relying on it)
- **DESIGN** chosen in the build plan
- **INVENTED** a placeholder, to be replaced by evidence
- **DERIVED** arithmetic on other rows

| # | Item | Value | Tag | Note |
|---|---|---|---|---|
| A-01 | Annual payout volume | $1.8B | BRIEF | |
| A-02 | Merchants | 45,000 | BRIEF | The source pages use it without saying whether it is from the brief or the call. Confirm. |
| A-03 | Fraud loss baseline | 48 bps | BRIEF | A floor, still maturing (A-14) |
| A-04 | Fraud loss target | 15 bps or less | BRIEF | Needs a defined measure and date (KPI 1) |
| A-05 | Annual loss at baseline | about $8.6M | DERIVED | $1.8B x 0.48% |
| A-06 | Annual loss at target | about $2.7M | DERIVED | $1.8B x 0.15% |
| A-07 | False positives now / target | 14% / 3.5% | BRIEF | Counting unit unclear (KPI 3 and 4) |
| A-08 | Auto-resolution now / target | 82% / 92% | BRIEF | Human-queue share is the same number again (KPI 6) |
| A-09 | Hot-path latency target | p99 under 150 ms | BRIEF | In-process only |
| A-10 | Gray-zone latency | p95 under 6 s, limit 8 s | BRIEF | The hold may break "Instant" |
| A-11 | Score thresholds | 0.45 and 0.82 | BRIEF | The brief never states the cost ratio (A-16), so they are unfitted |
| A-12 | Free-pass amount | $2,500 | BRIEF | Loophole closed by dollar velocity (Phase 1) |
| A-13 | Agent cost cap | $0.03 per case | BRIEF | A unit-price cap, not a total |
| A-14 | Fraud found within 14 days | about 85% | DISCOVERY | |
| A-15 | Takeover cases found only by the merchant calling | about 40% | DISCOVERY | |
| A-16 | Cost of a missed fraud vs a wrongly blocked merchant | 25 to 70 times | DISCOVERY | The mock call gave a range, not a figure |
| A-17 | Top-200 merchants' share of volume | about 40% | DISCOVERY | |
| A-18 | Max tool calls per case | 4 | DESIGN | |
| A-19 | AI-approval cap | $1,000 | INVENTED | Replace with evidence from Phase 5 |
| A-20 | Hold deadline | 10 s | INVENTED | Agent timeout plus 2 s margin |
| A-21 | Human response target, ESCALATED | 15 min | INVENTED | |
| A-22 | Human response target, FAST_HUMAN_LANE | 5 min | INVENTED | |
| A-23 | Synthetic population size | 20,000 payouts | DESIGN | Matches the earlier rules test |
| A-24 | Synthetic fraud shape | all except the 48 bps rate | INVENTED | Every effect size depends on the generator |
| A-25 | Gray-zone labelled cases | about 80 | DESIGN | Wide confidence intervals; report them |

Rows move from INVENTED to evidence as phases finish. When a value changes, add a line to the decision log.
