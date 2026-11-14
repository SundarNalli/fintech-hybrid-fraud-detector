import pytest
from fastapi.testclient import TestClient

from hybrid_fraud.agent.providers import ProviderError
from hybrid_fraud.core.schemas import PayoutState as S, Route
from hybrid_fraud.eval.scripted_investigator import ScriptedInvestigator
from hybrid_fraud.service.api import create_app
from hybrid_fraud.service.gray_zone import GrayZoneProcessor
from tests.helpers import Clock, submit_until


@pytest.fixture
def held(make_service, dataset, replayed):
    """A service with one payout held for review. Returns (service, db path, payout, clock)."""
    clock = Clock()
    service, path = make_service(clock)
    payout, _, _ = submit_until(service, dataset, replayed, Route.PENDING_REVIEW)
    return service, path, payout, clock


def processor(service, path, provider, thresholds):
    return GrayZoneProcessor(service, path, provider, thresholds)


def test_a_held_payout_is_resolved_by_the_policy_wrapper_and_the_ledger_shows_it(held, thresholds):
    service, path, payout, _ = held
    out = processor(service, path, ScriptedInvestigator(), thresholds).process(payout.payout_id)
    assert out.applied and out.final_state in (S.APPROVED, S.BLOCKED, S.ESCALATED)
    rows = service.ledger_rows(payout.payout_id)
    assert [r.to_state for r in rows][-2:] == ["PENDING_REVIEW", out.final_state.value]
    assert service.verify_ledger() == (True, None)


def test_a_payout_that_is_no_longer_held_is_left_alone(held, thresholds):
    service, path, payout, clock = held
    clock.t += 60
    service.reap()
    assert processor(service, path, ScriptedInvestigator(), thresholds).process(payout.payout_id) is None


class Fabricator:
    """A model that fetches evidence, then recommends APPROVE citing a record it never saw."""

    def __init__(self):
        self._real = ScriptedInvestigator()

    def complete(self, messages, tools, *, case_id, temperature=0.0, timeout=None):
        from hybrid_fraud.agent.providers import ProviderResponse, ToolCall
        resp = self._real.complete(messages, tools, case_id=case_id)
        if not any(m["role"] == "tool" for m in messages):
            return resp  # first turn: ask for the four tools as usual
        claim = {"field": "account_age_days", "op": "gte", "value": 365, "kind": "positive",
                 "evidence_id": "merchant_profile:m_never_fetched"}
        args = {"action": "APPROVE", "reason_codes": ["fabricated"], "claims": [claim, claim]}
        import json
        return ProviderResponse(tool_calls=[ToolCall(name="submit_recommendation", arguments=json.dumps(args))])


def test_a_fabricated_citation_is_rejected_and_the_payout_goes_to_a_human(held, thresholds):
    service, path, payout, _ = held
    out = processor(service, path, Fabricator(), thresholds).process(payout.payout_id)
    assert out.verifier_rejected and out.claims_ungrounded == 2
    assert out.final_state == S.ESCALATED and "GUARD_VERIFICATION_FAILED" in out.reason_codes
    assert service.status(payout.payout_id).state == S.ESCALATED


def test_a_model_that_errors_out_leaves_the_payout_escalated_never_approved(held, thresholds):
    service, path, payout, _ = held

    class Broken:
        def complete(self, *a, **kw):
            raise ProviderError("network error")

    out = processor(service, path, Broken(), thresholds).process(payout.payout_id)
    assert out.final_state == S.ESCALATED and out.stop_reason == "agent_provider_error"


def test_a_hold_that_expired_while_the_agent_was_thinking_is_not_overwritten(held, thresholds):
    service, path, payout, clock = held
    inner = ScriptedInvestigator()

    class Slow:
        def complete(self, *a, **kw):
            clock.t += 600  # the deadline passes during the model call
            service.reap()
            return inner.complete(*a, **kw)

    out = processor(service, path, Slow(), thresholds).process(payout.payout_id)
    assert out.applied is False
    assert service.status(payout.payout_id).state == S.ESCALATED
    assert service.ledger_rows(payout.payout_id)[-1].decided_by == "timeout"


def test_over_http_a_held_payout_is_handed_to_the_agent_after_the_response(make_service, dataset, replayed, thresholds):
    clock = Clock()
    service, path = make_service(clock)
    first = next(i for i, r in enumerate(replayed) if r.result.route == Route.PENDING_REVIEW)
    for p in dataset.payouts[:first]:
        service.submit(p, f"key_{p.payout_id}")
    gray = processor(service, path, ScriptedInvestigator(), thresholds)
    with TestClient(create_app(service, reap_interval=3600, gray_zone=gray)) as client:
        p = dataset.payouts[first]
        r = client.post("/api/payouts", json=p.model_dump(mode="json"), headers={"Idempotency-Key": "kh"})
        assert r.json()["state"] == "PENDING_REVIEW"  # the hot path answered fast, with the hold
        status = client.get(f"/api/payouts/{p.payout_id}").json()
        assert status["state"] != "PENDING_REVIEW"  # the agent path then resolved it
