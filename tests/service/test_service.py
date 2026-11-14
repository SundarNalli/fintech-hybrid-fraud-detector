import pytest

from hybrid_fraud.audit.states import IllegalTransition
from hybrid_fraud.core.schemas import FinalDecision, PayoutState as S, Route
from hybrid_fraud.service.payout_service import IdempotencyConflict
from hybrid_fraud.store.sqlite_lookup import UnknownMerchant
from tests.helpers import Clock, submit_until


def count(service, table):
    return service._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_an_ordinary_payout_is_approved_with_a_reason_and_two_ledger_rows(make_service, dataset):
    service, _ = make_service()
    r = service.submit(dataset.payouts[0], "k0")
    assert r.state == S.APPROVED and r.reason_codes
    assert [x.to_state for x in service.ledger_rows(r.payout_id)] == ["RECEIVED", "APPROVED"]


def test_a_repeated_request_returns_the_same_decision_and_writes_nothing_new(make_service, dataset):
    service, _ = make_service()
    first = service.submit(dataset.payouts[0], "k0")
    payouts_before, ledger_before = count(service, "payouts"), count(service, "ledger")
    again = service.submit(dataset.payouts[0], "k0")
    assert again.replayed and again.model_copy(update={"replayed": False}) == first
    assert (count(service, "payouts"), count(service, "ledger")) == (payouts_before, ledger_before)


def test_reusing_a_key_for_a_different_payout_is_a_conflict(make_service, dataset):
    service, _ = make_service()
    service.submit(dataset.payouts[0], "k0")
    with pytest.raises(IdempotencyConflict):
        service.submit(dataset.payouts[1], "k0")


def test_reusing_a_payout_id_under_a_new_key_is_a_conflict(make_service, dataset):
    service, _ = make_service()
    service.submit(dataset.payouts[0], "k0")
    with pytest.raises(IdempotencyConflict):
        service.submit(dataset.payouts[0], "another_key")


def test_an_unknown_merchant_is_rejected_and_nothing_is_stored(make_service, dataset):
    service, _ = make_service()
    bad = dataset.payouts[0].model_copy(update={"merchant_id": "m_nobody"})
    with pytest.raises(UnknownMerchant):
        service.submit(bad, "k_bad")
    assert (count(service, "payouts"), count(service, "ledger")) == (0, 0)


def test_a_failed_write_rolls_back_the_payout_and_the_ledger_stays_valid(make_service, dataset, monkeypatch):
    service, _ = make_service()
    service.submit(dataset.payouts[0], "k0")
    real = service._ledger.append
    calls = {"n": 0}

    def flaky(*a, **kw):
        calls["n"] += 1
        if calls["n"] == 2:  # the second ledger row of the next payout
            raise RuntimeError("disk full")
        return real(*a, **kw)

    monkeypatch.setattr(service._ledger, "append", flaky)
    with pytest.raises(RuntimeError):
        service.submit(dataset.payouts[1], "k1")
    monkeypatch.undo()
    assert count(service, "payouts") == 1 and service.verify_ledger() == (True, None)
    assert service.submit(dataset.payouts[1], "k1").state  # the retry works


def test_a_gray_payout_is_held_with_a_deadline(make_service, dataset, replayed):
    clock = Clock()
    service, _ = make_service(clock)
    _, r, _ = submit_until(service, dataset, replayed, Route.PENDING_REVIEW)
    assert r.state == S.PENDING_REVIEW and r.hold_deadline == clock.t + 10


def test_a_hold_is_left_alone_before_its_deadline_and_escalated_after_it(make_service, dataset, replayed):
    clock = Clock()
    service, _ = make_service(clock)
    p, r, _ = submit_until(service, dataset, replayed, Route.PENDING_REVIEW)
    clock.t += 9
    assert service.reap() == []
    clock.t += 2
    assert service.reap() == [p.payout_id]
    assert service.reap() == []  # running it again changes nothing
    assert service.status(p.payout_id).state == S.ESCALATED
    last = service.ledger_rows(p.payout_id)[-1]
    assert last.decided_by == "timeout" and "HOLD_DEADLINE_EXPIRED" in last.reason_codes


def test_a_held_payout_can_be_resolved_once_and_only_forward(make_service, dataset, replayed):
    service, _ = make_service(Clock())
    p, _, _ = submit_until(service, dataset, replayed, Route.PENDING_REVIEW)
    final = FinalDecision(payout_id=p.payout_id, state=S.BLOCKED, decided_by="policy_wrapper",
                          reason_codes=["agent_block"], evidence_trace=["x"])
    service.resolve(p.payout_id, final)
    assert service.status(p.payout_id).state == S.BLOCKED
    with pytest.raises(IllegalTransition):
        service.resolve(p.payout_id, final.model_copy(update={"state": S.APPROVED}))
    assert service.status(p.payout_id).state == S.BLOCKED


def test_after_a_crash_and_restart_no_payout_is_stuck_in_a_hold(make_service, dataset, replayed):
    clock = Clock()
    service, path = make_service(clock)
    p, _, _ = submit_until(service, dataset, replayed, Route.PENDING_REVIEW)
    # The process dies here: the old service is simply abandoned. Time passes.
    clock.t += 60
    restarted, _ = make_service(clock, db=path)
    assert restarted.status(p.payout_id).state == S.ESCALATED
    assert restarted.verify_ledger() == (True, None)


def test_velocity_survives_a_restart(make_service, dataset, thresholds):
    """The third of several near-$2,500 payouts is stopped even if the service restarts between them."""
    from datetime import timedelta
    base = next(p for p in dataset.payouts if p.merchant_id.startswith("m_f_s000"))
    service, path = make_service()
    routes = []
    for i in range(4):
        p = base.model_copy(update={"payout_id": f"burst_{i}", "amount_usd": 2400.0,
                                    "created_at": base.created_at + timedelta(minutes=5 * i)})
        if i == 2:
            service, _ = make_service(db=path)  # restart before the third payout
        routes.append(service.submit(p, f"kb_{i}").route)
    assert routes[2] == Route.BLOCK
