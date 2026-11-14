"""In-process velocity counters: count AND dollars, per merchant and per beneficiary.

A stand-in for Redis (decision D-003). The SQLite write-behind arrives in Phase 2.

Window semantics (decision D-011): a window of length W ending at time `now`
covers events with `now - W < ts <= now`. The lower edge is exclusive, the upper
inclusive. All times are timezone-aware UTC. The payout being scored counts as
part of its own window, so the numbers answer "what would the totals be if we
approved this one". Events must be recorded in time order.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta

from hybrid_fraud.core.schemas import Payout

HOUR = timedelta(hours=1)
DAY = timedelta(hours=24)


@dataclass(frozen=True)
class VelocitySnapshot:
    count_1h: int
    usd_1h: float
    usd_24h: float
    beneficiary_distinct_merchants_24h: int
    beneficiary_usd_24h: float
    first_time_payee: bool


class VelocityCounters:
    def __init__(self) -> None:
        self._by_merchant: dict[str, deque] = defaultdict(deque)  # (ts, usd)
        self._by_beneficiary: dict[str, deque] = defaultdict(deque)  # (ts, usd, merchant_id)
        self._seen_pairs: set[tuple[str, str]] = set()

    def snapshot(self, payout: Payout) -> VelocitySnapshot:
        """Totals for `payout` as if it were already counted. Does not record it."""
        now, usd = payout.created_at, payout.amount_usd
        m_events = self._window(self._by_merchant[payout.merchant_id], now, DAY)
        b_events = self._window(self._by_beneficiary[payout.beneficiary_id], now, DAY)

        last_hour = [e for e in m_events if e[0] > now - HOUR]
        merchants = {e[2] for e in b_events} | {payout.merchant_id}
        return VelocitySnapshot(
            count_1h=len(last_hour) + 1,
            usd_1h=sum(e[1] for e in last_hour) + usd,
            usd_24h=sum(e[1] for e in m_events) + usd,
            beneficiary_distinct_merchants_24h=len(merchants),
            beneficiary_usd_24h=sum(e[1] for e in b_events) + usd,
            first_time_payee=(payout.merchant_id, payout.beneficiary_id) not in self._seen_pairs,
        )

    def record(self, payout: Payout) -> None:
        """Count a payout. Call after scoring it, in time order."""
        self._by_merchant[payout.merchant_id].append((payout.created_at, payout.amount_usd))
        self._by_beneficiary[payout.beneficiary_id].append(
            (payout.created_at, payout.amount_usd, payout.merchant_id)
        )
        self._seen_pairs.add((payout.merchant_id, payout.beneficiary_id))

    def restore(self, recent: list[Payout], seen_pairs: set[tuple[str, str]]) -> None:
        """Rebuild after a restart. `recent` is the last 24 hours, in time order;
        `seen_pairs` is every (merchant, payee) pair ever paid."""
        for p in recent:
            self.record(p)
        self._seen_pairs |= seen_pairs

    @staticmethod
    def _window(events: deque, now: datetime, width: timedelta) -> list:
        while events and events[0][0] <= now - DAY:  # nothing older than 24 h is ever needed
            events.popleft()
        return [e for e in events if now - width < e[0] <= now]
