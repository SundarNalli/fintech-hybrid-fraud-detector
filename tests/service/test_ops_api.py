import pytest
from fastapi.testclient import TestClient

from hybrid_fraud.service.api import create_app
from hybrid_fraud.service.ops_api import demo_cases


@pytest.fixture
def client(make_service, dataset):
    service, _ = make_service()
    with TestClient(create_app(service, reap_interval=3600, dataset=dataset)) as c:
        yield c


def test_the_page_is_served_and_escapes_nothing_by_innerhtml(client):
    r = client.get("/")
    assert r.status_code == 200 and "Fraud ops" in r.text
    assert "innerHTML" not in r.text.replace("never innerHTML", "")  # merchant text must only go in as text


def test_every_demo_case_is_a_real_story_ending_on_its_target(dataset):
    cases = demo_cases(dataset)
    assert set(cases) == {"bustout", "takeover", "mule", "structuring", "missed", "ordinary"}
    for payouts in cases.values():
        assert payouts == sorted(payouts, key=lambda p: p.created_at)
        assert len({p.merchant_id for p in payouts}) == 1


def test_playing_a_case_fills_the_screen_and_playing_twice_changes_nothing(client):
    first = client.post("/api/ops/cases/structuring/play").json()
    assert first["submitted"] and not any(s["replayed"] for s in first["submitted"])
    again = client.post("/api/ops/cases/structuring/play").json()
    assert all(s["replayed"] for s in again["submitted"])
    summary = client.get("/api/ops/summary").json()
    assert summary["total"] == len(first["submitted"]) and summary["ledger_ok"] and summary["synthetic"]


def test_the_case_view_has_decision_ledger_and_marks_merchant_text_untrusted(client):
    pid = client.post("/api/ops/cases/ordinary/play").json()["submitted"][-1]["payout_id"]
    c = client.get(f"/api/ops/payouts/{pid}").json()
    assert c["decision"]["evidence_trace"] and c["ledger"] and c["chain_ok"]
    assert set(c["untrusted"]) == {"payout_memo", "beneficiary_name"}
    assert c["answer_key"]["is_fraud"] is False


def test_list_filters_by_state_and_rejects_an_unknown_one(client):
    client.post("/api/ops/cases/bustout/play")
    rows = client.get("/api/ops/payouts").json()
    assert rows and all(set(r) >= {"payout_id", "state", "score", "reason_codes"} for r in rows)
    only = client.get("/api/ops/payouts", params={"state": "BLOCKED"}).json()
    assert all(r["state"] == "BLOCKED" for r in only)
    assert client.get("/api/ops/payouts", params={"state": "NOPE"}).status_code == 422


def test_an_unknown_case_or_payout_is_a_404(client):
    assert client.post("/api/ops/cases/nope/play").status_code == 404
    assert client.get("/api/ops/payouts/nope").status_code == 404


def test_the_ops_api_has_no_way_to_decide_a_payout(client):
    paths = client.get("/openapi.json").json()["paths"]
    ops_writes = {p for p, methods in paths.items() if p.startswith("/api/ops") and set(methods) - {"get"}}
    assert ops_writes == {"/api/ops/cases/{case_id}/play"}
    assert not any("resolve" in p or "approve" in p for p in paths)
