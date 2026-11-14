"""The deterministic, asymmetric last word (decision log D-007).

Approving is irreversible, so it is hard. Escalating is cheap, so it is the
default whenever evidence is thin. The wrapper can only downgrade to
ESCALATED, never upgrade.
"""

from __future__ import annotations

from hybrid_fraud.core.config import Thresholds
from hybrid_fraud.core.schemas import (
    AgentAction,
    FinalDecision,
    Payout,
    PayoutState,
    VerifiedRecommendation,
)
from hybrid_fraud.guard import reason_codes as rc
from hybrid_fraud.guard.hard_facts import DEFAULT_HARD_FACTS, triggered

_TICKET_FACTS = ("2fa_ticket_last_48h", "credential_ticket")


def _trace(v: VerifiedRecommendation) -> list[str]:
    by_id = {r.evidence_id: r for r in v.evidence}
    return [
        f"{c.evidence_id}: {c.field} {c.op} {c.value!r} "
        f"(actual {by_id[c.evidence_id].fields.get(c.field)!r})"
        for c in v.claims
    ]


def _escalate(v: VerifiedRecommendation, codes: list[str], note: str) -> FinalDecision:
    return FinalDecision(
        payout_id=v.payout_id,
        state=PayoutState.ESCALATED,
        decided_by="policy_wrapper",
        reason_codes=[*v.reason_codes, *codes],
        evidence_trace=_trace(v),
        policy_note=note,
    )


def _approve_problems(
    v: VerifiedRecommendation, payout: Payout, t: Thresholds
) -> list[tuple[str, str]]:
    by_id = {r.evidence_id: r for r in v.evidence}
    # Merchant-written fields can raise suspicion but never vouch for the merchant.
    trusted = [
        c
        for c in v.claims
        if c.kind == "positive" and c.field not in by_id[c.evidence_id].merchant_authored
    ]
    problems: list[tuple[str, str]] = []
    if len(trusted) < 2:
        problems.append((
            rc.APPROVE_NEEDS_TWO_TRUSTED_CLAIMS,
            f"only {len(trusted)} positive claim(s) on fields the merchant cannot write; need 2",
        ))
    graphs = [r for r in v.evidence if r.source == "entity_graph"]
    if not any(r.fields.get("graph_clean") is True for r in graphs):
        problems.append((rc.APPROVE_GRAPH_NOT_CLEAN, "no evidence that the entity graph is clean"))
    # The verifier already rejects these; checking again keeps this file safe on its own.
    if any(f.name in _TICKET_FACTS for f in triggered(DEFAULT_HARD_FACTS, v.evidence)):
        problems.append((rc.APPROVE_TICKET_PRESENT, "2FA or credential ticket present in evidence"))
    cap = t.agent.ai_approval_cap_usd
    if payout.amount_usd >= cap:
        problems.append((rc.APPROVE_OVER_CAP, f"amount {payout.amount_usd} is not under the AI cap {cap}"))
    return problems


def decide(
    verified: VerifiedRecommendation,
    payout: Payout,
    thresholds: Thresholds,
    merchant_is_top_200: bool,
) -> FinalDecision:
    if verified.action == AgentAction.APPROVE:
        problems = _approve_problems(verified, payout, thresholds)
        if problems:
            note = "APPROVE downgraded: " + "; ".join(msg for _, msg in problems)
            return _escalate(verified, [code for code, _ in problems], note)
        state = PayoutState.APPROVED

    elif verified.action == AgentAction.BLOCK:
        if not any(c.kind == "hard_signal" for c in verified.claims):
            return _escalate(verified, [rc.BLOCK_NO_HARD_SIGNAL], "BLOCK downgraded: no grounded hard signal")
        if merchant_is_top_200:
            # A wrong block on a big merchant is costly, so a human decides fast.
            return _escalate(
                verified, [rc.BLOCK_TOP_MERCHANT], "BLOCK sent to the fast human lane: top-200 merchant"
            )
        state = PayoutState.BLOCKED

    else:  # ESCALATE_HUMAN
        state = PayoutState.ESCALATED

    return FinalDecision(
        payout_id=verified.payout_id,
        state=state,
        decided_by="policy_wrapper",
        reason_codes=list(verified.reason_codes),
        evidence_trace=_trace(verified),
    )


def escalate_on_failure(payout_id: str, code: str, detail: str) -> FinalDecision:
    """Verification error, timeout or malformed output: a human looks, never an approval."""
    return FinalDecision(
        payout_id=payout_id,
        state=PayoutState.ESCALATED,
        decided_by="timeout" if code == rc.AGENT_TIMEOUT else "policy_wrapper",
        reason_codes=[code],
        evidence_trace=[],
        policy_note=f"Escalated because the AI path failed: {detail}",
    )
