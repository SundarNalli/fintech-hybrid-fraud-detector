# What this prototype does not prove

Read this before quoting any result. Everything here is a practice scenario on synthetic data.

## Not proven
- **That a real model is accurate, cheap or fast enough.** No real model has been run. The only agent results come from a scripted stand-in with a fixed rule.
- **That the agent beats the rules.** In this synthetic world the rules alone already meet the loss target (4.9 bps against 15). That is a property of how the data was generated.
- **That the numbers match a real business.** Fraud rate, fraud types, merchant mix and the share of missed fraud are invented. Thresholds are tagged BRIEF, DESIGN, INVENTED or POC in `config/thresholds.toml`; the invented ones are placeholders.
- **That the 15 bps loss target is reachable.** Real loss is only known after about 120 days.
- **Real-world latency.** The hot-path numbers are in-process with no network. Gray-zone latency has no figure.
- **Security.** There is no login, no roles and no encryption of stored data. The ops screen is read-only because of that.
- **Scale.** One process, one writer lock, SQLite.
- **Resistance to a determined attacker.** Injection tests are hand-written. The verifier checks claims against records; it does not check that they are the right records to look at.
- **Legal or regulatory fitness.** No compliance review has happened.

## Shown by tests in this repo
- A payout never moves backward in state, and a repeated request returns the stored decision; a changed body is rejected.
- Any failure on the gray path (provider error, timeout, malformed output, failed verification, expired hold) ends at a human, never at an approval.
- A claim that does not match a fetched record cannot reach a decision.
- Edits to stored ledger rows are rejected or detected.

These hold for the cases the tests cover, not for every possible input.

## Fix first
1. Run the live evaluation with a real model, the owner's own key and spend caps.
2. Rule work for the 23% of fraud the rules approve.
3. Store tool calls so the case view can show the agent's steps.
4. Replace the invented placeholders with business decisions.
