"""The agent's read-only view of the world, over a `mode=ro` SQLite connection.

There are no write methods, and the connection itself refuses writes, so the
guarantee holds even if code tried. Each repository is bound to one moment
(`as_of`, epoch seconds): the agent sees what was known when the payout arrived.

The field names are the contract in `core/repository.py`.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hybrid_fraud.core.schemas import EvidenceRecord
from hybrid_fraud.store.db import connect_readonly

HOUR, DAY = 3600.0, 86400.0
NEW_PAYEE_HOURS = 168  # a payee first seen within a week still counts as a graph link
MAX_NEIGHBOURS = 50


class SQLiteReadOnlyRepository:
    def __init__(self, db_path: str | Path, as_of: float):
        self._c: sqlite3.Connection = connect_readonly(db_path)
        self._as_of = as_of

    def close(self) -> None:
        self._c.close()

    def _row(self, sql: str, args: tuple, what: str):
        row = self._c.execute(sql, args).fetchone()
        if row is None:
            raise LookupError(what)
        return row

    def merchant_profile(self, merchant_id: str) -> EvidenceRecord:
        r = self._row("SELECT created_at, sector, mcc_code, avg_daily_volume_30d, chargeback_rate_90d,"
                      " is_top_200, kyb_text FROM merchants WHERE merchant_id=?", (merchant_id,), merchant_id)
        return EvidenceRecord(
            evidence_id=f"merchant_profile:{merchant_id}", source="merchant_profile",
            fields={"account_age_days": round((self._as_of - r[0]) / DAY, 2), "sector": r[1], "mcc_code": r[2],
                    "avg_daily_volume_30d": r[3], "chargeback_rate_90d": r[4], "is_top_200": bool(r[5]),
                    "kyb_text": r[6]},
            merchant_authored=frozenset({"kyb_text"}))

    def _neighbours(self, merchant_id: str) -> set[str]:
        """Merchants one step away: same device, or same recently created payee."""
        t = self._as_of
        by_device = self._c.execute(
            "SELECT DISTINCT d2.merchant_id FROM device_links d1 JOIN device_links d2 ON d1.device_id=d2.device_id"
            " WHERE d1.merchant_id=? AND d1.first_seen_at<=? AND d2.first_seen_at<=? AND d2.merchant_id<>?",
            (merchant_id, t, t, merchant_id))
        by_payee = self._c.execute(
            "SELECT DISTINCT l2.merchant_id FROM beneficiary_links l1"
            " JOIN beneficiaries b ON b.beneficiary_id=l1.beneficiary_id"
            " JOIN beneficiary_links l2 ON l2.beneficiary_id=l1.beneficiary_id"
            " WHERE l1.merchant_id=? AND l1.added_at<=? AND l2.added_at<=? AND l2.merchant_id<>?"
            " AND b.first_seen_at>?", (merchant_id, t, t, merchant_id, t - NEW_PAYEE_HOURS * HOUR))
        return {r[0] for r in by_device} | {r[0] for r in by_payee}

    def entity_graph(self, merchant_id: str) -> EvidenceRecord:
        t = self._as_of
        shared = self._c.execute(
            "SELECT COALESCE(MAX(n), 1) FROM (SELECT COUNT(DISTINCT d2.merchant_id) AS n FROM device_links d1"
            " JOIN device_links d2 ON d1.device_id=d2.device_id WHERE d1.merchant_id=? AND d1.first_seen_at<=?"
            " AND d2.first_seen_at<=? GROUP BY d1.device_id)", (merchant_id, t, t)).fetchone()[0]
        neighbours = sorted(self._neighbours(merchant_id))[:MAX_NEIGHBOURS]
        flagged = sum(1 for n in neighbours if self._c.execute(
            "SELECT 1 FROM beneficiary_links l JOIN beneficiaries b ON b.beneficiary_id=l.beneficiary_id"
            " WHERE l.merchant_id=? AND b.on_mule_list=1 LIMIT 1", (n,)).fetchone())
        return EvidenceRecord(
            evidence_id=f"entity_graph:{merchant_id}", source="entity_graph",
            fields={"shared_device_merchants": shared, "linked_merchants_2hop": len(neighbours),
                    "mule_flagged_neighbors": flagged, "graph_clean": flagged == 0 and shared < 3})

    def support_tickets(self, merchant_id: str) -> EvidenceRecord:
        t = self._as_of
        rows = self._c.execute("SELECT category, text FROM tickets WHERE merchant_id=? AND created_at>? AND created_at<=?"
                               " ORDER BY created_at", (merchant_id, t - 48 * HOUR, t)).fetchall()
        return EvidenceRecord(
            evidence_id=f"support_tickets:{merchant_id}", source="support_tickets",
            fields={"ticket_count_48h": len(rows), "has_2fa_ticket_48h": any(r[0] == "2fa" for r in rows),
                    "has_credential_ticket_48h": any(r[0] == "credential" for r in rows),
                    "ticket_text": rows[-1][1] if rows else ""},
            merchant_authored=frozenset({"ticket_text"}))

    def beneficiary_history(self, beneficiary_id: str) -> EvidenceRecord:
        t = self._as_of
        b = self._row("SELECT name, first_seen_at, on_mule_list FROM beneficiaries WHERE beneficiary_id=?",
                      (beneficiary_id,), beneficiary_id)
        merchants, settled = self._c.execute(
            "SELECT COUNT(DISTINCT merchant_id), COALESCE(SUM(state='APPROVED'), 0) FROM payouts"
            " WHERE beneficiary_id=? AND created_at>? AND created_at<=?",
            (beneficiary_id, t - 30 * DAY, t)).fetchone()
        return EvidenceRecord(
            evidence_id=f"beneficiary_history:{beneficiary_id}", source="beneficiary_history",
            fields={"beneficiary_age_hrs": round(max(0.0, (t - b[1]) / HOUR), 2), "distinct_merchants_30d": merchants,
                    "settled_payouts_30d": settled, "on_mule_list": bool(b[2]), "beneficiary_name": b[0]},
            merchant_authored=frozenset({"beneficiary_name"}))
