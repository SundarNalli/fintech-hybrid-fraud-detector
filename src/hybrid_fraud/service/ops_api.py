"""The ops screen's API. Mostly reads; the only write is "play a demo case", which
submits ordinary payouts through the same `service.submit` as everything else.

Nothing here can approve, block or release a payout. A human decision button is
not built, on purpose: it needs a login and an audit identity first (see docs/decision-log.md D-023).
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from hybrid_fraud.core.schemas import PayoutState, Route
from hybrid_fraud.service.gray_zone import GrayZoneProcessor
from hybrid_fraud.service.payout_service import PayoutNotFound, PayoutService
from hybrid_fraud.sim.models import Dataset
from hybrid_fraud.sim.replay import replay

STATIC = Path(__file__).parent / "static"
LABELS = {  # demo cases: one story per kind of fraud, plus an ordinary one
    "bustout": "Bust-out: a new account cashes out fast",
    "takeover": "Account takeover: a lockout ticket, then a new payee",
    "mule": "Mule ring: one payee fed by many merchants",
    "structuring": "Structuring: many payouts just under a limit",
    "missed": "A miss, shown on purpose: fraud the rules approved",
    "ordinary": "An ordinary payout from an established merchant",
}


_replays: dict[int, list] = {}


def _replay_cached(ds: Dataset) -> list:
    if id(ds) not in _replays:
        _replays[id(ds)] = replay(ds)
    return _replays[id(ds)]


def demo_cases(ds: Dataset) -> dict[str, list]:
    """For each kind, the first matching payout plus that merchant's earlier payouts from the same 24 hours,
    in order, so the velocity counters see the same story the rules were built for."""
    truth = {l.payout_id: l for l in ds.labels}
    by_merchant: dict[str, list] = {}
    for p in ds.payouts:
        by_merchant.setdefault(p.merchant_id, []).append(p)

    def story(target) -> list:
        lo = target.created_at - timedelta(hours=24)
        return [p for p in by_merchant[target.merchant_id] if lo < p.created_at <= target.created_at]

    # A rules-only replay tells us which fraud the rules act on, so each story shows the system working.
    routes = {p.payout_id: row.result.route for p, row in zip(ds.payouts, _replay_cached(ds))}
    cases: dict[str, list] = {}
    for p in ds.payouts:
        label = truth[p.payout_id]
        if not label.is_fraud:
            continue
        if routes[p.payout_id] != Route.APPROVE and label.fraud_type not in cases:
            cases[label.fraud_type] = story(p)
        if routes[p.payout_id] == Route.APPROVE and "missed" not in cases:
            cases["missed"] = story(p)  # shown on purpose: the rules let this fraud through
    ordinary = next(p for p in ds.payouts if not truth[p.payout_id].is_fraud and p.amount_usd > 1000)
    cases["ordinary"] = story(ordinary)
    return cases


def ops_router(service: PayoutService, dataset: Dataset | None = None,
               gray_zone: GrayZoneProcessor | None = None, mode: str = "replay") -> APIRouter:
    r = APIRouter()
    cases = demo_cases(dataset) if dataset else {}
    truth = {l.payout_id: l for l in dataset.labels} if dataset else {}

    @r.get("/", include_in_schema=False)
    def page() -> FileResponse:
        return FileResponse(STATIC / "ops.html")

    @r.get("/api/ops/summary")
    def summary() -> dict:
        ok, bad = service.verify_ledger()
        counts = service.counts_by_state()
        return {"counts": counts, "total": sum(counts.values()), "ledger_ok": ok, "first_bad_seq": bad,
                "mode": mode, "synthetic": True}

    @r.get("/api/ops/payouts")
    def payouts(state: str | None = None, limit: int = 50) -> list[dict]:
        if state and state not in PayoutState.__members__:
            raise HTTPException(422, "unknown state")
        return service.list_payouts(state, max(1, min(limit, 200)))

    @r.get("/api/ops/payouts/{payout_id}")
    def case(payout_id: str) -> dict:
        """Everything the case view shows. `untrusted` lists fields a merchant typed: shown, never obeyed."""
        try:
            status = service.status(payout_id)
            payout = service.payout(payout_id)
        except PayoutNotFound:
            raise HTTPException(404, "no such payout")
        ok, bad = service.verify_ledger()
        label = truth.get(payout_id)
        return {
            "payout": payout.model_dump(mode="json"), "untrusted": ["payout_memo", "beneficiary_name"],
            "state": status.state.value, "decision": status.decision.model_dump(mode="json"),
            "ledger": [row.__dict__ for row in service.ledger_rows(payout_id)],
            "chain_ok": ok, "first_bad_seq": bad,
            # The answer key. The service never reads this; it is shown so a demo can say who was right.
            "answer_key": None if label is None else {"is_fraud": label.is_fraud, "fraud_type": label.fraud_type},
        }

    @r.get("/api/ops/cases")
    def list_cases() -> list[dict]:
        return [{"id": k, "title": LABELS[k], "payouts": len(v)} for k, v in cases.items()]

    @r.post("/api/ops/cases/{case_id}/play")
    def play(case_id: str, background: BackgroundTasks) -> dict:
        if case_id not in cases:
            raise HTTPException(404, "no such demo case")
        out = []
        for p in cases[case_id]:
            resp = service.submit(p, f"demo-{p.payout_id}")  # same key every time: playing twice is a replay
            if gray_zone and resp.state == PayoutState.PENDING_REVIEW and not resp.replayed:
                background.add_task(gray_zone.process, resp.payout_id)
            out.append({"payout_id": resp.payout_id, "state": resp.state.value, "replayed": resp.replayed})
        return {"case": case_id, "submitted": out}

    return r
