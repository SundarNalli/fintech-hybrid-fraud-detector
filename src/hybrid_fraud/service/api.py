"""The HTTP surface. A thin layer: it validates input, calls the service, maps errors."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException

from hybrid_fraud.audit.ledger import LedgerRow
from hybrid_fraud.audit.states import IllegalTransition
from hybrid_fraud.core.schemas import Payout, PayoutState
from hybrid_fraud.service.gray_zone import GrayZoneProcessor
from hybrid_fraud.service.payout_service import (
    IdempotencyConflict, PayoutNotFound, PayoutResponse, PayoutService, PayoutStatus,
)
from hybrid_fraud.store.sqlite_lookup import UnknownMerchant


def create_app(service: PayoutService, reap_interval: float = 1.0,
               gray_zone: GrayZoneProcessor | None = None) -> FastAPI:
    """With a `gray_zone` processor, a held payout is handed to the agent after the response goes out.
    Without one, a hold waits for `resolve()` or the reaper."""
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async def reaper():
            while True:  # holds past their deadline go to the human queue
                await asyncio.sleep(reap_interval)
                await asyncio.to_thread(service.reap)

        task = asyncio.create_task(reaper())
        yield
        task.cancel()

    app = FastAPI(title="Hybrid fraud detector (synthetic data only)", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict:
        return {"ok": True, "synthetic": True}

    @app.post("/api/payouts", response_model=PayoutResponse)
    def submit_payout(payout: Payout, background: BackgroundTasks,
                      idempotency_key: str | None = Header(default=None)) -> PayoutResponse:
        if not idempotency_key:
            raise HTTPException(400, "Idempotency-Key header is required")
        try:
            response = service.submit(payout, idempotency_key)
            if gray_zone and response.state == PayoutState.PENDING_REVIEW and not response.replayed:
                background.add_task(gray_zone.process, response.payout_id)  # runs after the response is sent
            return response
        except IdempotencyConflict as e:
            raise HTTPException(409, str(e))
        except UnknownMerchant as e:
            raise HTTPException(422, f"unknown merchant {e}")

    @app.get("/api/payouts/{payout_id}", response_model=PayoutStatus)
    def payout_status(payout_id: str) -> PayoutStatus:
        try:
            return service.status(payout_id)
        except PayoutNotFound:
            raise HTTPException(404, "no such payout")

    @app.get("/api/payouts/{payout_id}/ledger")
    def payout_ledger(payout_id: str) -> dict:
        rows: list[LedgerRow] = service.ledger_rows(payout_id)
        if not rows:
            raise HTTPException(404, "no such payout")
        ok, bad = service.verify_ledger()
        return {"chain_ok": ok, "first_bad_seq": bad, "rows": [r.__dict__ for r in rows]}

    return app
