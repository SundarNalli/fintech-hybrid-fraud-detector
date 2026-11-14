"""Small builders so each test shows only what makes it different."""

from datetime import datetime, timezone

from hybrid_fraud.core.schemas import (
    AgentAction,
    Claim,
    EvidenceRecord,
    Payout,
    Recommendation,
)
from hybrid_fraud.guard.hard_facts import DEFAULT_HARD_FACTS
from hybrid_fraud.guard.verifier import verify

APPROVE = AgentAction.APPROVE
BLOCK = AgentAction.BLOCK
ESCALATE = AgentAction.ESCALATE_HUMAN


def make_payout(amount: float = 500.0) -> Payout:
    return Payout(
        payout_id="p1", merchant_id="m1", beneficiary_id="b1", amount_usd=amount,
        rail="ach", beneficiary_name="Acme", payout_memo="rent", device_id="d1",
        created_at=datetime(2026, 11, 14, tzinfo=timezone.utc),
    )


def profile(**extra) -> EvidenceRecord:
    fields = {"account_age_days": 900, "kyb_text": "verified by us", **extra}
    return EvidenceRecord(
        evidence_id="merchant_profile:m1", source="merchant_profile", fields=fields,
        merchant_authored=frozenset({"kyb_text"}),
    )


def graph(**extra) -> EvidenceRecord:
    fields = {"graph_clean": True, "shared_device_merchants": 1, **extra}
    return EvidenceRecord(evidence_id="entity_graph:m1", source="entity_graph", fields=fields)


def tickets(**fields) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id="support_tickets:m1", source="support_tickets", fields=fields,
        merchant_authored=frozenset({"ticket_text"}),
    )


def claim(evidence_id, field, op, value, kind="positive") -> Claim:
    return Claim(field=field, op=op, value=value, evidence_id=evidence_id, kind=kind)


GOOD_APPROVE_CLAIMS = [
    claim("merchant_profile:m1", "account_age_days", "gte", 365),
    claim("entity_graph:m1", "shared_device_merchants", "eq", 1),
]


def run_verify(action, claims, records, hard_facts=DEFAULT_HARD_FACTS):
    rec = Recommendation(action=action, reason_codes=["R"], claims=claims)
    return verify(rec, records, "p1", hard_facts)
