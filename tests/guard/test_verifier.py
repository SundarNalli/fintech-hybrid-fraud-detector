import pytest

from hybrid_fraud.guard.verifier import VerificationError
from tests.guard.conftest import (
    APPROVE,
    BLOCK,
    GOOD_APPROVE_CLAIMS,
    claim,
    graph,
    profile,
    run_verify,
    tickets,
)


def test_a_claim_citing_an_evidence_id_that_was_never_fetched_is_rejected():
    fake = claim("merchant_profile:m999", "account_age_days", "gte", 365)
    with pytest.raises(VerificationError) as e:
        run_verify(APPROVE, [fake], [profile(), graph()])
    assert "unknown evidence_id" in e.value.failures[0]


def test_a_real_evidence_id_with_a_false_predicate_is_rejected():
    lie = claim("merchant_profile:m1", "account_age_days", "gte", 5000)
    with pytest.raises(VerificationError) as e:
        run_verify(APPROVE, [lie], [profile(), graph()])
    assert "claim false" in e.value.failures[0]


def test_a_claim_about_a_missing_field_counts_as_false():
    with pytest.raises(VerificationError):
        run_verify(APPROVE, [claim("entity_graph:m1", "no_such_field", "eq", 1)], [graph()])


def test_approve_is_contradicted_by_a_recent_2fa_ticket():
    records = [profile(), graph(), tickets(twofa_ticket_last_48h=True)]
    with pytest.raises(VerificationError) as e:
        run_verify(APPROVE, GOOD_APPROVE_CLAIMS, records)
    assert "contradicts hard fact" in e.value.failures[0]


def test_block_is_not_contradicted_by_a_2fa_ticket():
    records = [tickets(twofa_ticket_last_48h=True)]
    claims = [claim("support_tickets:m1", "twofa_ticket_last_48h", "eq", True, "hard_signal")]
    assert run_verify(BLOCK, claims, records).action == BLOCK


def test_every_failure_is_reported_not_just_the_first():
    claims = [claim("x:1", "a", "eq", 1), claim("y:2", "b", "eq", 2)]
    with pytest.raises(VerificationError) as e:
        run_verify(APPROVE, claims, [graph()])
    assert len(e.value.failures) == 2


def test_a_fully_grounded_recommendation_passes_and_keeps_its_evidence():
    v = run_verify(APPROVE, GOOD_APPROVE_CLAIMS, [profile(), graph()])
    assert [r.evidence_id for r in v.evidence] == ["merchant_profile:m1", "entity_graph:m1"]
