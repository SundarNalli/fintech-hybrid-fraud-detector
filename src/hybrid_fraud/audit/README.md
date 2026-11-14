# audit

The append-only decision ledger. Every state change of a payout is a row.

| File | What |
|---|---|
| `states.py` | The lifecycle and the forward-only rule. Final states have no way out |
| `ledger.py` | The ledger. Triggers reject UPDATE and DELETE; each row hashes its content with the previous row's hash; `verify()` recomputes the chain |
| `trace.py` | Renders ledger rows as readable lines. Pure templating, no model |

Honest limit: a hash chain shows a row was changed or removed from the middle. It cannot show rows were cut off the end (D-017).

*Built in Phase 2.*
