import sqlite3
from datetime import timedelta

import pytest

from hybrid_fraud.store.readonly_repository import SQLiteReadOnlyRepository


@pytest.fixture
def repo_at(full_run, dataset):
    path, _ = full_run
    opened = []

    def make(as_of):
        r = SQLiteReadOnlyRepository(path, as_of.timestamp())
        opened.append(r)
        return r

    yield make
    for r in opened:
        r.close()


def test_the_repository_refuses_writes_at_the_database(repo_at, dataset):
    repo = repo_at(dataset.payouts[-1].created_at)
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        repo._c.execute("DELETE FROM merchants")
    assert not [m for m in dir(repo) if m.startswith(("insert", "update", "delete", "write", "set_"))]


def test_each_tool_returns_the_field_names_of_the_contract(repo_at, dataset):
    p = dataset.payouts[-1]
    repo = repo_at(p.created_at)
    assert {"account_age_days", "sector", "mcc_code", "avg_daily_volume_30d", "chargeback_rate_90d",
            "is_top_200", "kyb_text"} <= set(repo.merchant_profile(p.merchant_id).fields)
    assert {"shared_device_merchants", "linked_merchants_2hop", "mule_flagged_neighbors",
            "graph_clean"} <= set(repo.entity_graph(p.merchant_id).fields)
    assert {"ticket_count_48h", "has_2fa_ticket_48h", "has_credential_ticket_48h",
            "ticket_text"} <= set(repo.support_tickets(p.merchant_id).fields)
    assert {"beneficiary_age_hrs", "distinct_merchants_30d", "settled_payouts_30d", "on_mule_list",
            "beneficiary_name"} <= set(repo.beneficiary_history(p.beneficiary_id).fields)


def test_text_the_merchant_can_write_is_marked_merchant_authored(repo_at, dataset):
    p = dataset.payouts[-1]
    repo = repo_at(p.created_at)
    assert repo.merchant_profile(p.merchant_id).merchant_authored == {"kyb_text"}
    assert repo.support_tickets(p.merchant_id).merchant_authored == {"ticket_text"}
    assert repo.beneficiary_history(p.beneficiary_id).merchant_authored == {"beneficiary_name"}


def test_a_ticket_opened_after_the_payout_is_not_visible_to_the_agent(repo_at, dataset):
    t = next(t for t in dataset.tickets if t.category in ("2fa", "credential"))
    before = repo_at(t.created_at - timedelta(seconds=1)).support_tickets(t.merchant_id)
    after = repo_at(t.created_at).support_tickets(t.merchant_id)
    assert after.fields["ticket_count_48h"] == before.fields["ticket_count_48h"] + 1


def test_a_mule_victim_is_linked_to_the_other_victims_through_the_new_payee(repo_at, dataset):
    mule_times = [p.created_at for p, l in zip(dataset.payouts, dataset.labels) if l.fraud_type == "mule"]
    repo = repo_at(max(mule_times) + timedelta(hours=1))
    graph = repo.entity_graph("m_f_m000")
    assert graph.fields["linked_merchants_2hop"] >= 3


def test_beneficiary_history_counts_merchants_who_paid_them(repo_at, dataset):
    mule_times = [p.created_at for p, l in zip(dataset.payouts, dataset.labels) if l.fraud_type == "mule"]
    h = repo_at(max(mule_times) + timedelta(hours=1)).beneficiary_history("ben_x_mule")
    assert h.fields["distinct_merchants_30d"] == 4 and h.fields["on_mule_list"] is False


def test_an_unknown_merchant_raises_lookup_error(repo_at, dataset):
    with pytest.raises(LookupError):
        repo_at(dataset.payouts[0].created_at).merchant_profile("m_nobody")
