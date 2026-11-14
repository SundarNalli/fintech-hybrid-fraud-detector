"""The guard and the repository must spell their fields the same way.

An earlier merge had the guard looking for `twofa_ticket_last_48h` while the
repository returned `has_2fa_ticket_48h`: every hard fact silently never fired,
and a takeover ticket could not stop an approval. These tests use the real
repository's output so that cannot happen again.
"""

from datetime import timedelta

from hybrid_fraud.core.schemas import AgentAction, Recommendation
from hybrid_fraud.guard.hard_facts import DEFAULT_HARD_FACTS, triggered
from hybrid_fraud.guard.verifier import VerificationError, verify
from hybrid_fraud.sim.scenarios import scenarios
from hybrid_fraud.store.readonly_repository import SQLiteReadOnlyRepository

import pytest


def all_repository_fields(db_path, dataset) -> set[str]:
    p = dataset.payouts[-1]
    repo = SQLiteReadOnlyRepository(db_path, p.created_at.timestamp())
    try:
        records = [repo.merchant_profile(p.merchant_id), repo.entity_graph(p.merchant_id),
                   repo.support_tickets(p.merchant_id), repo.beneficiary_history(p.beneficiary_id)]
    finally:
        repo.close()
    return {f for r in records for f in r.fields}


def test_every_hard_fact_names_a_field_the_real_repository_returns(full_run, dataset):
    fields = all_repository_fields(full_run[0], dataset)
    missing = [f.field for f in DEFAULT_HARD_FACTS if f.field not in fields]
    assert missing == []


def test_a_credential_ticket_in_real_evidence_triggers_the_hard_fact_and_blocks_an_approve():
    sc = next(s for s in scenarios() if s.name.startswith("3"))  # locked out two hours ago
    assert [f.name for f in triggered(DEFAULT_HARD_FACTS, sc.evidence)] == ["credential_ticket"]
    approve = Recommendation(action=AgentAction.APPROVE, reason_codes=["x"], claims=[])
    with pytest.raises(VerificationError, match="credential_ticket"):
        verify(approve, sc.evidence, sc.payout.payout_id, DEFAULT_HARD_FACTS)


def test_a_clean_scenario_triggers_no_hard_fact():
    sc = next(s for s in scenarios() if s.name.startswith("4"))
    assert triggered(DEFAULT_HARD_FACTS, sc.evidence) == []
