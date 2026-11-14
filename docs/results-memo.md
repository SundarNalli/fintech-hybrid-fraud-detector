# Results memo: the pipeline run

> Practice scenario, synthetic data. **No real model has been run yet.** Everything below comes from a scripted stand-in that follows a fixed rule. The full tables are in [eval-results.md](eval-results.md) (clean run) and [eval-fault-injection.md](eval-fault-injection.md) (10% of cases made deliberately wrong).

## What this run does show

1. **The whole path works end to end.** A payout the rules hold goes agent, verifier, policy wrapper, then the ledger. Every failure ends at a human: provider errors, timeouts, malformed output, a rejected verification, a hold that expired mid-call. Nothing on that path can approve a payout the policy wrapper did not.
2. **The verifier catches careless mistakes.** With 10% of cases made wrong (a citation to a record that was never fetched, or a false value), all 5 cases with a bad claim were rejected and sent to humans. Decisions built on an ungrounded claim: 0. A test repeats this at 30%.
3. **Integration found a real hole.** The guard looked for `twofa_ticket_last_48h` while the repository returned `has_2fa_ticket_48h`, so on real evidence none of the hard facts could fire and a takeover ticket could not stop an approval. Each side's own tests passed. It is fixed, and a test now checks every hard-fact field against the real repository's output.
4. **The approval cap, not the agent, decides how much gets approved.** The script recommended approval on 33 held payouts. The policy wrapper let 3 through and sent 30 to a human for being over the $1,000 cap. That cap is an invented placeholder (A-19). If it stays near that value, the AI approval path does little, and the agent's value is mostly in the evidence behind blocks and escalations. The right cap is a business decision nobody has made.

## What this run cannot show

- **How good a real model is.** The stand-in's wrong-call rate (4 of 25 decided, 16%) comes from its own rule, which blocks on any two-factor ticket and so blocks four legitimate merchants that really did open one. It says nothing about a model.
- **Cost per extra fraud caught.** The earlier ceiling put it at $0.38 to $0.53 and expected the measured figure to be higher. Not measured.
- **Gray-zone latency.** The 8-second hold may be hard to meet with up to five model round trips. Not measured.
- **Repeatability.** Trivially 100% for a script.
- **Whether the agent is needed.** In this synthetic world the rules alone already beat the loss target (4.9 bps against 15), because the fraud they miss is small-dollar. The world cannot argue for the agent on loss grounds, and that is a property of how it was generated, not evidence either way.

## What missed target

- The agent cannot reach 22 of the 96 fraud payouts (23%). The rules approve them, so they never become gray cases, and even a perfect oracle leaves them. Closing that gap is a job for the rules.
- Gray-zone latency, cost and model accuracy have no real figures yet.

## To get real numbers

```bash
# Set OPENROUTER_API_KEY, LLM_MODEL and both LLM_*_USD_PER_MTOK prices in .env first.
python -m hybrid_fraud.eval.run --provider live --max-cases 20          # prints the worst-case cost, sends nothing
python -m hybrid_fraud.eval.run --provider live --max-cases 20 --confirm --max-usd 0.50 --out docs/eval-live.md
```

Start small. A live run needs `--confirm`, refuses to run without prices (so spend can be metered), and stops at its dollar cap.
