"""The hot path's questions, answered from SQLite. Same protocol as `sim.lookup.DatasetLookup`.

A test checks that the two give identical decisions on every synthetic payout.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

HOUR = 3600.0
DAY = 86400.0


class UnknownMerchant(LookupError):
    pass


class SQLiteLookup:
    def __init__(self, conn: sqlite3.Connection):
        self._c = conn

    def account_age_days(self, merchant_id: str, at: datetime) -> float:
        row = self._c.execute("SELECT created_at FROM merchants WHERE merchant_id=?", (merchant_id,)).fetchone()
        if row is None:
            raise UnknownMerchant(merchant_id)
        return (at.timestamp() - row[0]) / DAY

    def merchant_stats(self, merchant_id: str) -> tuple[float, float, bool]:
        row = self._c.execute(
            "SELECT avg_daily_volume_30d, chargeback_rate_90d, is_top_200 FROM merchants WHERE merchant_id=?",
            (merchant_id,)).fetchone()
        if row is None:
            raise UnknownMerchant(merchant_id)
        return row[0], row[1], bool(row[2])

    def beneficiary_facts(self, merchant_id: str, beneficiary_id: str, at: datetime) -> tuple[float, float, bool]:
        now = at.timestamp()
        link = self._c.execute("SELECT added_at FROM beneficiary_links WHERE merchant_id=? AND beneficiary_id=?",
                               (merchant_id, beneficiary_id)).fetchone()
        bene = self._c.execute("SELECT first_seen_at, on_mule_list FROM beneficiaries WHERE beneficiary_id=?",
                               (beneficiary_id,)).fetchone()
        # A payee we have no record of is new: it was added just now.
        added = link[0] if link else now
        first_seen, mule = (bene[0], bool(bene[1])) if bene else (now, False)
        return max(0.0, (now - added) / HOUR), max(0.0, (now - first_seen) / HOUR), mule

    def shared_device_merchants(self, device_id: str, at: datetime) -> int:
        row = self._c.execute("SELECT COUNT(DISTINCT merchant_id) FROM device_links WHERE device_id=? AND first_seen_at<=?",
                              (device_id, at.timestamp())).fetchone()
        return max(1, row[0])  # at least the merchant itself

    def recent_ticket_flags(self, merchant_id: str, at: datetime) -> tuple[bool, bool]:
        now = at.timestamp()
        cats = {r[0] for r in self._c.execute(
            "SELECT DISTINCT category FROM tickets WHERE merchant_id=? AND created_at>? AND created_at<=?",
            (merchant_id, now - 48 * HOUR, now))}
        return "2fa" in cats, "credential" in cats
