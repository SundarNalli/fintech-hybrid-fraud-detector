"""The payout service: one call in, one decision out, every step on the ledger.

    submit(payout, idempotency_key)
        repeat key, same body   -> the stored decision, nothing new written
        repeat key, other body  -> IdempotencyConflict
        new                     -> features -> rules -> route -> payout row + ledger rows, one transaction

Holds (PENDING_REVIEW) carry a deadline. `reap()` moves any hold past its
deadline to ESCALATED, and runs again on startup, so a crash never leaves a
payout waiting forever: hold state lives in SQLite, not in memory.

One lock serialises writers. That is simple and honest for a prototype; the
latency numbers include any waiting on it.
"""

from __future__ import annotations

import hashlib
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Callable

from pydantic import BaseModel, ConfigDict

from hybrid_fraud.audit.ledger import Ledger, LedgerRow
from hybrid_fraud.core.config import Thresholds
from hybrid_fraud.core.reason_codes import ReasonCode
from hybrid_fraud.core.schemas import FinalDecision, Payout, PayoutState, Route
from hybrid_fraud.hot_path.features import build_features
from hybrid_fraud.hot_path.router import route
from hybrid_fraud.hot_path.velocity import DAY, VelocityCounters
from hybrid_fraud.store.sqlite_lookup import SQLiteLookup

ROUTE_TO_STATE = {
    Route.APPROVE: PayoutState.APPROVED,
    Route.BLOCK: PayoutState.BLOCKED,
    Route.FAST_HUMAN_LANE: PayoutState.ESCALATED,
    Route.PENDING_REVIEW: PayoutState.PENDING_REVIEW,
}


class IdempotencyConflict(Exception):
    pass


class PayoutNotFound(LookupError):
    pass


class PayoutResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    payout_id: str
    state: PayoutState
    route: Route
    reason_codes: list[str]
    evidence_trace: list[str]
    score: float
    novel_anomaly_flag: bool
    hold_deadline: float | None  # epoch seconds, only for holds
    replayed: bool = False  # true when this is a stored answer to a repeated request


class PayoutStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    payout_id: str
    state: PayoutState  # the current state, which may be later than the first decision
    decision: PayoutResponse  # what the hot path decided on arrival


class PayoutService:
    def __init__(self, conn: sqlite3.Connection, thresholds: Thresholds, clock: Callable[[], float] = time.time):
        self._conn, self._t, self._clock = conn, thresholds, clock
        self._lock = threading.RLock()
        self._lookup = SQLiteLookup(conn)
        self._counters = VelocityCounters()
        self._ledger = Ledger(conn)
        self.recover()

    # ---- the one call that matters -------------------------------------
    def submit(self, payout: Payout, idempotency_key: str) -> PayoutResponse:
        body_hash = hashlib.sha256(payout.model_dump_json().encode()).hexdigest()
        with self._lock:
            row = self._conn.execute("SELECT body_hash, response FROM payouts WHERE idempotency_key=?",
                                     (idempotency_key,)).fetchone()
            if row:
                if row[0] != body_hash:
                    raise IdempotencyConflict("this Idempotency-Key was used with a different payout")
                return PayoutResponse.model_validate_json(row[1]).model_copy(update={"replayed": True})
            if self._conn.execute("SELECT 1 FROM payouts WHERE payout_id=?", (payout.payout_id,)).fetchone():
                raise IdempotencyConflict("this payout_id was already submitted under another key")

            snapshot = self._counters.snapshot(payout)
            feats = build_features(payout, self._lookup, snapshot)  # raises UnknownMerchant
            result = route(feats, self._t)
            state = ROUTE_TO_STATE[result.route]
            now = self._clock()
            deadline = now + self._t.holds.deadline_seconds if state == PayoutState.PENDING_REVIEW else None
            response = PayoutResponse(
                payout_id=payout.payout_id, state=state, route=result.route,
                reason_codes=[c.value for c in result.reason_codes], evidence_trace=result.evidence_trace,
                score=result.score, novel_anomaly_flag=result.novel_anomaly_flag, hold_deadline=deadline)

            with self._tx():
                self._conn.execute("INSERT OR IGNORE INTO beneficiaries VALUES (?,?,?,0)",
                                   (payout.beneficiary_id, payout.beneficiary_name, payout.created_at.timestamp()))
                self._conn.execute("INSERT OR IGNORE INTO beneficiary_links VALUES (?,?,?)",
                                   (payout.merchant_id, payout.beneficiary_id, payout.created_at.timestamp()))
                self._conn.execute(
                    "INSERT INTO payouts (payout_id, idempotency_key, body_hash, merchant_id, beneficiary_id,"
                    " amount_usd, created_at, payload, state, response, hold_deadline) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (payout.payout_id, idempotency_key, body_hash, payout.merchant_id, payout.beneficiary_id,
                     payout.amount_usd, payout.created_at.timestamp(), payout.model_dump_json(), state.value,
                     response.model_dump_json(), deadline))
                self._ledger.append(payout.payout_id, None, PayoutState.RECEIVED, "hot_path", [], [], now)
                self._ledger.append(payout.payout_id, PayoutState.RECEIVED, state, "hot_path",
                                    response.reason_codes, result.evidence_trace, now)
            self._counters.record(payout)  # counted only once the decision is safely stored
            return response

    # ---- later steps ----------------------------------------------------
    def resolve(self, payout_id: str, final: FinalDecision) -> None:
        """Apply the policy wrapper's decision to a held payout."""
        with self._lock:
            self._move(payout_id, final.state, final.decided_by, final.reason_codes, final.evidence_trace,
                       final.policy_note)

    def reap(self, now: float | None = None) -> list[str]:
        """Escalate every hold past its deadline. Safe to call at any time, any number of times."""
        now = self._clock() if now is None else now
        with self._lock:
            ids = [r[0] for r in self._conn.execute(
                "SELECT payout_id FROM payouts WHERE state=? AND hold_deadline<=? ORDER BY hold_deadline",
                (PayoutState.PENDING_REVIEW.value, now))]
            for pid in ids:
                self._move(pid, PayoutState.ESCALATED, "timeout", [ReasonCode.HOLD_DEADLINE_EXPIRED.value],
                           ["no decision before the hold deadline; sent to the human queue"])
            return ids

    def recover(self) -> None:
        """Rebuild the in-memory counters from stored payouts, then escalate stale holds."""
        with self._lock:
            rows = self._conn.execute("SELECT payload, created_at FROM payouts ORDER BY created_at, payout_id").fetchall()
            if rows:
                latest = rows[-1][1]
                window = DAY.total_seconds()  # DAY is a timedelta; created_at is epoch seconds
                recent = [Payout.model_validate_json(r[0]) for r in rows if r[1] > latest - window]
                pairs = set(self._conn.execute("SELECT DISTINCT merchant_id, beneficiary_id FROM payouts").fetchall())
                self._counters = VelocityCounters()
                self._counters.restore(recent, pairs)
            self.reap()

    # ---- reads ----------------------------------------------------------
    def status(self, payout_id: str) -> PayoutStatus:
        with self._lock:
            row = self._conn.execute("SELECT state, response FROM payouts WHERE payout_id=?", (payout_id,)).fetchone()
        if row is None:
            raise PayoutNotFound(payout_id)
        return PayoutStatus(payout_id=payout_id, state=PayoutState(row[0]),
                            decision=PayoutResponse.model_validate_json(row[1]))

    def payout(self, payout_id: str) -> Payout:
        """The payout exactly as it was submitted."""
        with self._lock:
            row = self._conn.execute("SELECT payload FROM payouts WHERE payout_id=?", (payout_id,)).fetchone()
        if row is None:
            raise PayoutNotFound(payout_id)
        return Payout.model_validate_json(row[0])

    def list_payouts(self, state: str | None = None, limit: int = 50) -> list[dict]:
        """Newest first, for the ops screen. Plain dicts: this is a display read, not a decision input."""
        sql = ("SELECT p.payout_id, p.state, p.merchant_id, p.amount_usd, p.created_at, p.response, m.legal_name"
               " FROM payouts p LEFT JOIN merchants m ON m.merchant_id = p.merchant_id")
        args: list = []
        if state:
            sql += " WHERE p.state=?"
            args.append(state)
        sql += " ORDER BY p.rowid DESC LIMIT ?"
        args.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, args).fetchall()
        out = []
        for pid, st, mid, amount, created, resp, name in rows:
            r = PayoutResponse.model_validate_json(resp)
            out.append({"payout_id": pid, "state": st, "route": r.route.value, "merchant_id": mid,
                        "merchant_name": name, "amount_usd": amount, "created_at": created,
                        "score": r.score, "reason_codes": r.reason_codes})
        return out

    def counts_by_state(self) -> dict[str, int]:
        with self._lock:
            return dict(self._conn.execute("SELECT state, COUNT(*) FROM payouts GROUP BY state").fetchall())

    def merchant_is_top_200(self, merchant_id: str) -> bool:
        with self._lock:
            return self._lookup.merchant_stats(merchant_id)[2]

    def ledger_rows(self, payout_id: str) -> list[LedgerRow]:
        with self._lock:
            return self._ledger.rows_for(payout_id)

    def verify_ledger(self) -> tuple[bool, int | None]:
        with self._lock:
            return self._ledger.verify()

    # ---- internals ------------------------------------------------------
    def _move(self, payout_id: str, new: PayoutState, by: str, reasons: list[str], trace: list[str],
              note: str = "") -> None:
        row = self._conn.execute("SELECT state FROM payouts WHERE payout_id=?", (payout_id,)).fetchone()
        if row is None:
            raise PayoutNotFound(payout_id)
        with self._tx():
            # The ledger checks the move is forward-only before anything is written.
            self._ledger.append(payout_id, PayoutState(row[0]), new, by, reasons, trace, self._clock(), note)
            self._conn.execute("UPDATE payouts SET state=?, hold_deadline=NULL WHERE payout_id=?",
                               (new.value, payout_id))

    @contextmanager
    def _tx(self):
        head = self._ledger.head
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self._conn.execute("ROLLBACK")
            self._ledger.rewind(head)
            raise
        else:
            self._conn.execute("COMMIT")
