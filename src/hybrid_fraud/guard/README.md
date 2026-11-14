# guard

Where the AI's advice is checked. Two steps, in order:

1. `verifier.py`: every claim must cite a record fetched for this case and be true against that record's fields (a missing field is false), and the recommendation must not contradict a hard fact (`hard_facts.py`, e.g. a 2FA ticket forbids APPROVE). Failure raises `VerificationError`. This is the only module that builds a `VerifiedRecommendation`.
2. `policy_wrapper.py`: the deterministic, asymmetric final decision (D-007). It accepts only a `VerifiedRecommendation`.
   - APPROVE needs two positive claims on fields the merchant cannot write, a clean graph, no 2FA or credential ticket, and an amount under the cap. Otherwise ESCALATED.
   - BLOCK needs one grounded hard signal, and a top-200 merchant's BLOCK goes to the fast human lane (ESCALATED). Otherwise ESCALATED.
   - Verification error, timeout or malformed output all go through `escalate_on_failure`: always ESCALATED, never an approval.

Also here: `predicates.py` (the one true/false check for a claim), `reason_codes.py` (guard strings), `injection_hygiene.py` (`wrap_untrusted` fences memos, names and ticket text as data for the prompt).

Promise: zero ungrounded claims. Wrong conclusions are reported separately (KPI 11).
