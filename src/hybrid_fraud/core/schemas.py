"""Shared vocabulary: the small set of types every other folder agrees on.

Nothing here makes a decision. If two folders need to exchange data, the type
lives here.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Scalar = str | int | float | bool | None


class Route(StrEnum):
    """Where the hot path sends a payout."""

    APPROVE = "APPROVE"
    BLOCK = "BLOCK"
    FAST_HUMAN_LANE = "FAST_HUMAN_LANE"  # top-200 merchants: a human, quickly
    PENDING_REVIEW = "PENDING_REVIEW"  # hold; the gray-zone agent looks at it


class AgentAction(StrEnum):
    """What the agent may recommend. It can never approve or block by itself."""

    APPROVE = "APPROVE"
    BLOCK = "BLOCK"
    ESCALATE_HUMAN = "ESCALATE_HUMAN"


class PayoutState(StrEnum):
    """Forward-only lifecycle of a payout. Every move is a ledger row."""

    RECEIVED = "RECEIVED"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"
    ESCALATED = "ESCALATED"  # in the human queue


class Payout(BaseModel):
    """One payout request, as known at payout time. Labels live elsewhere."""

    model_config = ConfigDict(frozen=True)

    payout_id: str
    merchant_id: str
    beneficiary_id: str
    amount_usd: float = Field(gt=0)
    rail: str
    beneficiary_name: str  # merchant-authored: attacker-controlled
    payout_memo: str  # merchant-authored: attacker-controlled
    device_id: str
    created_at: datetime
    synthetic: Literal[True] = True  # every record in this repo is generated


# --------------------------------------------------------------------------
# Evidence: what the agent's tools return, and what claims must point at.
# --------------------------------------------------------------------------

EvidenceSource = Literal[
    "merchant_profile", "entity_graph", "support_tickets", "beneficiary_history"
]


class EvidenceRecord(BaseModel):
    """One record returned by a read-only tool.

    `merchant_authored` names the fields in `fields` that the merchant (or an
    attacker) can write. Those can raise suspicion but never count as positive
    evidence for an approval (decision log D-007).
    """

    model_config = ConfigDict(frozen=True)

    evidence_id: str  # stable, e.g. "merchant_profile:m_000123"
    source: EvidenceSource
    fields: dict[str, Scalar]
    merchant_authored: frozenset[str] = frozenset()


Op = Literal["eq", "ne", "gt", "gte", "lt", "lte", "contains"]
ClaimKind = Literal["positive", "hard_signal"]


class Claim(BaseModel):
    """A typed predicate the verifier can check: `record.fields[field] <op> value`."""

    model_config = ConfigDict(frozen=True)

    field: str
    op: Op
    value: Scalar
    evidence_id: str
    kind: ClaimKind


class Recommendation(BaseModel):
    """What the agent returns via `submit_recommendation`. Untrusted until verified."""

    model_config = ConfigDict(frozen=True)

    action: AgentAction
    reason_codes: list[str]
    claims: list[Claim] = []
    narrative: str = ""  # free text; shown labelled as the model's words, never used to decide


class VerifiedRecommendation(BaseModel):
    """A recommendation that passed the verifier.

    Only `guard.verifier.verify()` may construct one. The policy wrapper accepts
    nothing else. A test fails if code outside that module builds one.
    """

    model_config = ConfigDict(frozen=True)

    payout_id: str
    action: AgentAction
    reason_codes: list[str]
    claims: list[Claim]
    narrative: str
    evidence: list[EvidenceRecord]  # the exact records the claims were checked against
    verifier_version: str


class FinalDecision(BaseModel):
    """The last word on a payout, written to the audit ledger."""

    model_config = ConfigDict(frozen=True)

    payout_id: str
    state: PayoutState
    decided_by: Literal["hot_path", "policy_wrapper", "human_queue", "timeout"]
    reason_codes: list[str]
    evidence_trace: list[str]  # human-readable lines built from real field values
    policy_note: str = ""  # set when the policy wrapper overrode the agent
