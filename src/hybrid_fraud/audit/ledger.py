"""The audit ledger: append-only, and tamper-evident.

Two protections, both testable:
  1. SQLite triggers reject UPDATE and DELETE on the table.
  2. Each row stores a hash of its own content plus the previous row's hash.
     If someone drops the triggers and edits a row, `verify()` finds it.

Honest limit: a hash chain shows that a row was changed or removed from the
middle. It cannot show that rows were cut off the end. Copying the head hash
somewhere else (a log, an email) closes that gap in a real deployment.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass

from hybrid_fraud.audit.states import check_transition
from hybrid_fraud.core.schemas import PayoutState

GENESIS = "0" * 64

DDL = """
CREATE TABLE IF NOT EXISTS ledger (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    payout_id TEXT NOT NULL,
    from_state TEXT,
    to_state TEXT NOT NULL,
    decided_by TEXT NOT NULL,
    reason_codes TEXT NOT NULL,
    evidence_trace TEXT NOT NULL,
    policy_note TEXT NOT NULL,
    at REAL NOT NULL,
    prev_hash TEXT NOT NULL,
    hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ledger_payout ON ledger(payout_id, seq);
CREATE TRIGGER IF NOT EXISTS ledger_no_update BEFORE UPDATE ON ledger
BEGIN SELECT RAISE(ABORT, 'ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ledger_no_delete BEFORE DELETE ON ledger
BEGIN SELECT RAISE(ABORT, 'ledger is append-only'); END;
"""


@dataclass(frozen=True)
class LedgerRow:
    seq: int
    payout_id: str
    from_state: str | None
    to_state: str
    decided_by: str
    reason_codes: list[str]
    evidence_trace: list[str]
    policy_note: str
    at: float
    hash: str


def _digest(prev_hash, payout_id, from_state, to_state, decided_by, reasons, trace, note, at) -> str:
    body = json.dumps([prev_hash, payout_id, from_state, to_state, decided_by, reasons, trace, note, at],
                      separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(body.encode()).hexdigest()


class Ledger:
    """Bound to a connection. The caller owns the transaction, so a payout row and its
    ledger rows commit together or not at all."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        conn.executescript(DDL)
        row = conn.execute("SELECT hash FROM ledger ORDER BY seq DESC LIMIT 1").fetchone()
        self._head = row[0] if row else GENESIS

    @property
    def head(self) -> str:
        return self._head

    def rewind(self, head: str) -> None:
        """Forget in-memory chain progress after the caller rolled a transaction back."""
        self._head = head

    def append(self, payout_id: str, from_state: PayoutState | None, to_state: PayoutState, decided_by: str,
               reason_codes: list[str], evidence_trace: list[str], at: float, policy_note: str = "") -> None:
        check_transition(from_state, to_state)  # forward-only, enforced where the rows are written
        f = from_state.value if from_state else None
        h = _digest(self._head, payout_id, f, to_state.value, decided_by, reason_codes, evidence_trace, policy_note, at)
        self._conn.execute(
            "INSERT INTO ledger (payout_id, from_state, to_state, decided_by, reason_codes, evidence_trace,"
            " policy_note, at, prev_hash, hash) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (payout_id, f, to_state.value, decided_by, json.dumps(reason_codes), json.dumps(evidence_trace),
             policy_note, at, self._head, h))
        self._head = h

    def rows_for(self, payout_id: str) -> list[LedgerRow]:
        cur = self._conn.execute(
            "SELECT seq, payout_id, from_state, to_state, decided_by, reason_codes, evidence_trace,"
            " policy_note, at, hash FROM ledger WHERE payout_id=? ORDER BY seq", (payout_id,))
        return [LedgerRow(r[0], r[1], r[2], r[3], r[4], json.loads(r[5]), json.loads(r[6]), r[7], r[8], r[9])
                for r in cur.fetchall()]

    def verify(self) -> tuple[bool, int | None]:
        """Recompute every hash from the start. Returns (ok, first bad seq)."""
        prev = GENESIS
        for r in self._conn.execute(
            "SELECT seq, payout_id, from_state, to_state, decided_by, reason_codes, evidence_trace, policy_note,"
            " at, prev_hash, hash FROM ledger ORDER BY seq"
        ):
            expected = _digest(prev, r[1], r[2], r[3], r[4], json.loads(r[5]), json.loads(r[6]), r[7], r[8])
            if r[9] != prev or r[10] != expected:
                return False, r[0]
            prev = r[10]
        return True, None
