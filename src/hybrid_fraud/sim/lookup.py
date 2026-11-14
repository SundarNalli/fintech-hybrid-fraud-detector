"""Answer the hot path's questions from an in-memory Dataset.

Phase 2 replaces this with a SQLite version behind the same protocol. Nothing
here touches `dataset.labels`.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from hybrid_fraud.sim.models import Dataset

HOURS = 3600.0


class DatasetLookup:
    def __init__(self, ds: Dataset):
        self._merchants = {m.merchant_id: m for m in ds.merchants}
        self._benes = {b.beneficiary_id: b for b in ds.beneficiaries}
        self._links = {(l.merchant_id, l.beneficiary_id): l for l in ds.beneficiary_links}
        self._devices: dict[str, list] = defaultdict(list)
        for l in ds.device_links:
            self._devices[l.device_id].append(l)
        self._tickets: dict[str, list] = defaultdict(list)
        for t in ds.tickets:
            self._tickets[t.merchant_id].append(t)

    def account_age_days(self, merchant_id: str, at: datetime) -> float:
        return (at - self._merchants[merchant_id].created_at).total_seconds() / 86400

    def merchant_stats(self, merchant_id: str) -> tuple[float, float, bool]:
        m = self._merchants[merchant_id]
        return m.avg_daily_volume_30d, m.chargeback_rate_90d, m.is_top_200

    def beneficiary_facts(self, merchant_id: str, beneficiary_id: str, at: datetime) -> tuple[float, float, bool]:
        link, bene = self._links[(merchant_id, beneficiary_id)], self._benes[beneficiary_id]
        return (
            max(0.0, (at - link.added_at).total_seconds() / HOURS),
            max(0.0, (at - bene.first_seen_at).total_seconds() / HOURS),
            bene.on_mule_list,
        )

    def shared_device_merchants(self, device_id: str, at: datetime) -> int:
        """Merchants seen on this device by `at`. A login not yet made is not yet known."""
        return len({l.merchant_id for l in self._devices[device_id] if l.first_seen_at <= at})

    def recent_ticket_flags(self, merchant_id: str, at: datetime) -> tuple[bool, bool]:
        since = at - timedelta(hours=48)
        recent = [t for t in self._tickets[merchant_id] if since < t.created_at <= at]
        return (any(t.category == "2fa" for t in recent), any(t.category == "credential" for t in recent))
