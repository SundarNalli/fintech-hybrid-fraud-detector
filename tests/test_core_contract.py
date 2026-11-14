import pytest
from pydantic import ValidationError

from hybrid_fraud.core.config import load_thresholds
from hybrid_fraud.core.schemas import (
    AgentAction,
    Claim,
    EvidenceRecord,
    Recommendation,
)


def test_thresholds_load_with_the_brief_values():
    t = load_thresholds()
    assert t.gate1.approve_below == 0.45
    assert t.gate1.block_at_or_above == 0.82
    assert t.agent.max_tool_calls == 4


def test_evidence_records_are_immutable():
    rec = EvidenceRecord(
        evidence_id="merchant_profile:m_1",
        source="merchant_profile",
        fields={"account_age_days": 10},
    )
    with pytest.raises(ValidationError):
        rec.evidence_id = "something_else"


def test_a_recommendation_cannot_carry_an_unknown_action():
    with pytest.raises(ValidationError):
        Recommendation(action="REFUND", reason_codes=[])


def test_a_claim_is_a_typed_predicate():
    c = Claim(
        field="account_age_days", op="gte", value=400,
        evidence_id="merchant_profile:m_1", kind="positive",
    )
    assert c.op == "gte"
    assert AgentAction.ESCALATE_HUMAN.value == "ESCALATE_HUMAN"
