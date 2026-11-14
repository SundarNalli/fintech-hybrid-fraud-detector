# guard

Where the AI's advice is checked.

- `verifier.py`: schema, cited IDs present, each claim true against its record, no contradiction of a hard fact.
- `policy_wrapper.py`: the deterministic, asymmetric final decision. It accepts only a `VerifiedRecommendation`.

Promise: zero ungrounded claims. Wrong conclusions are reported separately.

*Built in Phase 4.*
