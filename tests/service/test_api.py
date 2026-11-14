import pytest
from fastapi.testclient import TestClient

from hybrid_fraud.service.api import create_app


@pytest.fixture
def client(make_service):
    service, _ = make_service()
    with TestClient(create_app(service, reap_interval=3600)) as c:
        yield c


def body(p):
    return p.model_dump(mode="json")


def test_a_payout_is_decided_over_http_with_reason_and_evidence(client, dataset):
    r = client.post("/api/payouts", json=body(dataset.payouts[0]), headers={"Idempotency-Key": "k0"})
    assert r.status_code == 200
    j = r.json()
    assert j["state"] == "APPROVED" and j["reason_codes"] and j["evidence_trace"] and j["replayed"] is False


def test_the_idempotency_key_is_required(client, dataset):
    assert client.post("/api/payouts", json=body(dataset.payouts[0])).status_code == 400


def test_a_repeat_returns_the_stored_decision_and_a_changed_body_is_a_conflict(client, dataset):
    h = {"Idempotency-Key": "k0"}
    client.post("/api/payouts", json=body(dataset.payouts[0]), headers=h)
    again = client.post("/api/payouts", json=body(dataset.payouts[0]), headers=h)
    assert again.status_code == 200 and again.json()["replayed"] is True
    assert client.post("/api/payouts", json=body(dataset.payouts[1]), headers=h).status_code == 409


def test_an_unknown_merchant_is_a_422(client, dataset):
    bad = body(dataset.payouts[0]) | {"merchant_id": "m_nobody"}
    assert client.post("/api/payouts", json=bad, headers={"Idempotency-Key": "kx"}).status_code == 422


def test_a_payout_not_marked_synthetic_is_refused(client, dataset):
    bad = body(dataset.payouts[0]) | {"synthetic": False}
    assert client.post("/api/payouts", json=bad, headers={"Idempotency-Key": "ks"}).status_code == 422


def test_status_and_ledger_endpoints(client, dataset):
    p = dataset.payouts[0]
    client.post("/api/payouts", json=body(p), headers={"Idempotency-Key": "k0"})
    assert client.get(f"/api/payouts/{p.payout_id}").json()["state"] == "APPROVED"
    ledger = client.get(f"/api/payouts/{p.payout_id}/ledger").json()
    assert ledger["chain_ok"] and [r["to_state"] for r in ledger["rows"]] == ["RECEIVED", "APPROVED"]
    assert client.get("/api/payouts/nope").status_code == 404
    assert client.get("/health").json()["synthetic"] is True
