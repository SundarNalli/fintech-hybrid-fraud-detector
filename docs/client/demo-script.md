# Demo script (about 12 minutes)

> Practice scenario. The company, merchants and every number are fictional and synthetic. Run it in replay mode (no API key). In replay mode no model runs: held payouts go to the human queue by the fail-safe path, and the demo says so out loud.

**Setup, 2 minutes before:** `make serve`, open http://127.0.0.1:8000/ , confirm the tags read "synthetic data only", "replay mode" and "ledger chain intact". Delete `data/local/fraud.db` first for an empty screen.

## The one-sentence frame
"A fast rules path decides the obvious payouts. A slow, checked AI path only advises on the gray ones. The AI advises; a plain program decides."

## Beats

| # | Click | Say | Point at |
|---|---|---|---|
| 1 | Play **An ordinary payout** | "Most traffic is boring. It is approved in milliseconds and the reason is written down." | The case view: reason codes, evidence trace, ledger timeline |
| 2 | Play **Structuring** (3 payouts) | "Several payouts just under a limit. Each looks fine alone; the dollar-velocity counter sees the pattern and a hard rule blocks the third. No AI involved, so no AI cost and no AI risk." | BLOCKED and the `DOLLAR_VELOCITY_STRUCTURING` code |
| 3 | Play **Bust-out** | "A new account moving a large amount. No hard rule is conclusive, so it is held, not decided." | State "pending review" and `NOVEL_ANOMALY_LARGE` |
| 4 | Play **Takeover** or **Mule ring** | "Also gray: held for review with a deadline. The mule case replays five payouts from several merchants to one payee." | State "pending review", then "escalated" a few seconds later |
| 5 | Stay on that case | "In replay mode there is no model, so the fail-safe applies: it goes to a human. Failing safe is the design." | The ledger rows: `hot_path`, then `policy_wrapper` or `timeout` |
| 6 | Play **A miss** | **The failure on purpose.** "The rules approved this fraud. The agent never sees it, because it only looks at held payouts. 23% of fraud payouts in this world are like this. Fixing it is a job for the rules, not for AI." | The APPROVED state next to the answer key line |
| 7 | Point at the header | "Every decision is in an append-only ledger with a hash chain. If someone edits history, this tag turns red." | "ledger chain intact" |

Which route each demo case takes depends on the synthetic data; check the screen before the call and adjust the wording if a case lands somewhere unexpected.

## Things that are shown by tests, not on screen
Say so plainly. Run `python -m pytest -q tests/service/test_gray_zone.py tests/agent/test_agent_loop.py tests/guard` live if asked.
- **Prompt-injection memo:** merchant text is fenced and marked untrusted for the model (`test_injected_text_is_fenced...`). The screen shows it as plain text.
- **Fabricated citation:** the verifier rejects it and the payout goes to a human (`test_a_fabricated_citation_is_rejected...`).
- **Agent timeout and expired hold:** both end at a human, and a late agent answer cannot overwrite the reaper's decision.

## What to say about numbers
Quote only what [results-memo.md](../results-memo.md) supports. In this synthetic world the rules alone already beat the loss target, and **no real model has been run**. Do not claim agent accuracy, cost per case or gray-zone latency; none are measured.

## Rehearsal questions (answer each in under 30 seconds)
1. *"What does the AI actually add?"* Evidence behind blocks and escalations. Whether it adds approvals depends on the approval cap, which is an invented placeholder (A-19).
2. *"Can it hallucinate?"* It can be wrong. It cannot act on an ungrounded claim: every claim must match a record it fetched, and the program decides.
3. *"Why not let the model approve everything it is confident about?"* The policy wrapper is asymmetric on purpose: the AI can push toward a block or a human easily, toward an approval only under a cap and with no hard facts against it.
4. *"What if the model is down?"* Held payouts escalate to the human queue at the deadline. The hot path never waits for a model.
5. *"Is this ready for production?"* No. See [what-this-does-not-prove.md](what-this-does-not-prove.md).
6. *"What would you do first?"* Shadow mode. See [pilot-proposal.md](pilot-proposal.md).
