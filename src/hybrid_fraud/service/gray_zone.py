"""The gray-zone path: a held payout goes through agent -> verifier -> policy wrapper.

    held payout
      -> agent        reads evidence through read-only tools, recommends   (may fail)
      -> verifier     every claim must be true against a record it fetched
      -> policy       deterministic, asymmetric, final authority
      -> service.resolve(...)   the ledger gets the decision

Whatever goes wrong at any step, the payout ends up ESCALATED (a human looks).
Nothing on this path can approve a payout that the policy wrapper has not.

The slow model call runs outside the service lock, so it never blocks the hot path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hybrid_fraud.agent.budget import Prices
from hybrid_fraud.agent.orchestrator import run_case
from hybrid_fraud.agent.providers import LlmProvider
from hybrid_fraud.audit.states import IllegalTransition
from hybrid_fraud.core.config import Thresholds
from hybrid_fraud.core.schemas import AgentAction, PayoutState
from hybrid_fraud.guard import reason_codes as rc
from hybrid_fraud.guard.hard_facts import DEFAULT_HARD_FACTS, HardFact
from hybrid_fraud.guard.policy_wrapper import decide, escalate_on_failure
from hybrid_fraud.guard.predicates import holds
from hybrid_fraud.guard.verifier import VerificationError, verify
from hybrid_fraud.service.payout_service import PayoutService
from hybrid_fraud.store.readonly_repository import SQLiteReadOnlyRepository


@dataclass(frozen=True)
class GrayZoneOutcome:
    payout_id: str
    agent_action: AgentAction  # what the agent recommended (an escalation if it failed)
    stop_reason: str  # "submitted", or why the agent stopped
    tool_calls: int
    cost_usd: float
    latency_seconds: float
    claims_total: int
    claims_ungrounded: int  # counted BEFORE the verifier: how often the model got it wrong
    verifier_rejected: bool
    final_state: PayoutState
    reason_codes: tuple[str, ...]
    applied: bool  # False if the hold was already resolved (for example by the reaper)


class GrayZoneProcessor:
    def __init__(self, service: PayoutService, db_path: str | Path, provider: LlmProvider, thresholds: Thresholds,
                 prices: Prices = Prices(), hard_facts: tuple[HardFact, ...] = DEFAULT_HARD_FACTS):
        self.service, self.db_path, self.provider = service, Path(db_path), provider
        self.t, self.prices, self.hard_facts = thresholds, prices, hard_facts

    def process(self, payout_id: str) -> GrayZoneOutcome | None:
        """Run one held payout to a decision. Returns None if it is no longer held."""
        if self.service.status(payout_id).state != PayoutState.PENDING_REVIEW:
            return None
        payout = self.service.payout(payout_id)

        repo = SQLiteReadOnlyRepository(self.db_path, payout.created_at.timestamp())
        try:
            result = run_case(payout, self.provider, repo, self.t.agent, self.prices)
        finally:
            repo.close()

        by_id = {r.evidence_id: r for r in result.evidence}
        claims = result.recommendation.claims
        ungrounded = sum(1 for c in claims
                         if c.evidence_id not in by_id or not holds(by_id[c.evidence_id].fields, c.field, c.op, c.value))

        rejected = False
        if result.stop_reason == "agent_timeout":
            final = escalate_on_failure(payout_id, rc.AGENT_TIMEOUT, "the agent ran out of time")
        else:
            try:
                verified = verify(result.recommendation, result.evidence, payout_id, self.hard_facts)
                final = decide(verified, payout, self.t, self.service.merchant_is_top_200(payout.merchant_id))
            except VerificationError as e:
                rejected = True
                final = escalate_on_failure(payout_id, rc.VERIFICATION_FAILED, "; ".join(e.failures))

        try:
            self.service.resolve(payout_id, final)
            applied = True
        except IllegalTransition:  # the hold deadline passed while the agent was thinking
            applied = False

        return GrayZoneOutcome(
            payout_id=payout_id, agent_action=result.recommendation.action, stop_reason=result.stop_reason,
            tool_calls=result.tool_calls, cost_usd=result.cost_usd, latency_seconds=result.latency_seconds,
            claims_total=len(claims), claims_ungrounded=ungrounded, verifier_rejected=rejected,
            final_state=final.state, reason_codes=tuple(final.reason_codes), applied=applied)
