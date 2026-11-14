"""KPI maths for the evaluation. Pure functions over final decisions, so they are easy to test.

Definitions follow docs/kpi-definitions.md. Every rate comes with a 95% Wilson interval,
because with about 100 fraud payouts and about 80 gray cases the uncertainty is wide.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from hybrid_fraud.core.schemas import PayoutState as S


@dataclass(frozen=True)
class Row:
    """One payout's final outcome under one system, with its label (labels only ever live here)."""

    payout_id: str
    merchant_id: str
    amount_usd: float
    is_fraud: bool
    is_top_200: bool
    state: S
    was_gray: bool  # held by the hot path, so the agent (or the oracle) decided it


@dataclass(frozen=True)
class Rate:
    k: int
    n: int

    @property
    def value(self) -> float:
        return self.k / self.n if self.n else float("nan")

    @property
    def interval(self) -> tuple[float, float]:
        return wilson(self.k, self.n)

    def fmt(self, digits: int = 1) -> str:
        if not self.n:
            return "n/a"
        lo, hi = self.interval
        return f"{self.k}/{self.n} = {self.value * 100:.{digits}f}% ({lo * 100:.{digits}f} to {hi * 100:.{digits}f})"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval. Behaves sensibly at 0 and n, unlike the textbook formula."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def n_state(rows: list[Row], state: S) -> int:
    return sum(1 for r in rows if r.state == state)


def summarise(rows: list[Row]) -> dict:
    fraud = [r for r in rows if r.is_fraud]
    legit = [r for r in rows if not r.is_fraud]
    paid = [r for r in rows if r.state == S.APPROVED]
    paid_usd = sum(r.amount_usd for r in paid)
    stolen_usd = sum(r.amount_usd for r in paid if r.is_fraud)

    def merchants_hit(rs):
        hit = {r.merchant_id for r in rs if not r.is_fraud and r.state in (S.BLOCKED, S.ESCALATED)}
        allm = {r.merchant_id for r in rs}
        return Rate(len(hit & allm), len(allm))

    top = [r for r in rows if r.is_top_200]
    return {
        "fraud_blocked": Rate(n_state(fraud, S.BLOCKED), len(fraud)),
        "fraud_held": Rate(n_state(fraud, S.ESCALATED), len(fraud)),
        "fraud_approved": Rate(n_state(fraud, S.APPROVED), len(fraud)),
        "fraud_caught_or_held": Rate(n_state(fraud, S.BLOCKED) + n_state(fraud, S.ESCALATED), len(fraud)),
        "stolen_usd": stolen_usd,
        "loss_bps": stolen_usd / paid_usd * 10000 if paid_usd else float("nan"),
        "legit_blocked": Rate(n_state(legit, S.BLOCKED), len(legit)),
        "legit_held": Rate(n_state(legit, S.ESCALATED), len(legit)),
        "merchants_hit": merchants_hit(rows),
        "top200_merchants_hit": merchants_hit(top),
        "auto_resolved": Rate(n_state(rows, S.APPROVED) + n_state(rows, S.BLOCKED), len(rows)),
    }


def gray_summary(rows: list[Row]) -> dict:
    """The held payouts only: what became of them, and how often the final call was wrong."""
    gray = [r for r in rows if r.was_gray]
    fraud, legit = [r for r in gray if r.is_fraud], [r for r in gray if not r.is_fraud]
    wrong = [r for r in gray if (r.is_fraud and r.state == S.APPROVED) or (not r.is_fraud and r.state == S.BLOCKED)]
    decided = [r for r in gray if r.state in (S.APPROVED, S.BLOCKED)]
    return {
        "cases": len(gray), "fraud": len(fraud), "legit": len(legit),
        "approved": Rate(n_state(gray, S.APPROVED), len(gray)),
        "blocked": Rate(n_state(gray, S.BLOCKED), len(gray)),
        "escalated": Rate(n_state(gray, S.ESCALATED), len(gray)),
        "wrong_of_decided": Rate(len(wrong), len(decided)),  # of the cases the system dared to decide
        "wrong_of_all": Rate(len(wrong), len(gray)),
        "fraud_blocked": Rate(n_state(fraud, S.BLOCKED), len(fraud)),
        "legit_approved": Rate(n_state(legit, S.APPROVED), len(legit)),
    }
