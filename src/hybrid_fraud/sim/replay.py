"""Replay the dataset through the hot path in time order, and summarise.

Run:  python -m hybrid_fraud.sim.replay

This is the rules-only system: nothing here calls a model. Labels are read only
at the very end, to score the decisions.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from hybrid_fraud.core.config import Thresholds, load_thresholds
from hybrid_fraud.core.schemas import Route
from hybrid_fraud.hot_path.features import PayoutFeatures, build_features
from hybrid_fraud.hot_path.router import HotPathResult, route
from hybrid_fraud.hot_path.velocity import VelocityCounters
from hybrid_fraud.sim.dataset_io import read_dataset
from hybrid_fraud.sim.lookup import DatasetLookup
from hybrid_fraud.sim.models import Dataset


@dataclass(frozen=True)
class ReplayRow:
    features: PayoutFeatures
    result: HotPathResult
    is_fraud: bool
    fraud_type: str | None


def replay(ds: Dataset, t: Thresholds | None = None) -> list[ReplayRow]:
    t = t or load_thresholds()
    lookup, counters = DatasetLookup(ds), VelocityCounters()
    labels = {l.payout_id: l for l in ds.labels}
    rows = []
    for payout in ds.payouts:  # already in time order
        feats = build_features(payout, lookup, counters.snapshot(payout))
        res = route(feats, t)
        counters.record(payout)  # counted only after it has been scored
        lab = labels[payout.payout_id]
        rows.append(ReplayRow(feats, res, lab.is_fraud, lab.fraud_type))
    return rows


def _pct(n: int, d: int) -> str:
    return f"{n}/{d} = {n / d * 100:.2f}%" if d else "0/0"


def summarise(rows: list[ReplayRow]) -> str:
    fraud = [r for r in rows if r.is_fraud]
    good = [r for r in rows if not r.is_fraud]
    by = lambda rs, route_: [r for r in rs if r.result.route == route_]
    out = [f"payouts {len(rows)}, fraud {len(fraud)}, legitimate {len(good)}", ""]
    out.append("route counts: " + ", ".join(f"{k.value} {v}" for k, v in Counter(r.result.route for r in rows).items()))
    out += [
        "",
        f"fraud blocked            {_pct(len(by(fraud, Route.BLOCK)), len(fraud))}",
        f"fraud held (gray/fast)   {_pct(len(by(fraud, Route.PENDING_REVIEW)) + len(by(fraud, Route.FAST_HUMAN_LANE)), len(fraud))}",
        f"fraud approved (missed)  {_pct(len(by(fraud, Route.APPROVE)), len(fraud))}",
        f"legit blocked            {_pct(len(by(good, Route.BLOCK)), len(good))}",
        f"legit held (gray/fast)   {_pct(len(by(good, Route.PENDING_REVIEW)) + len(by(good, Route.FAST_HUMAN_LANE)), len(good))}",
        "",
        "by fraud type (blocked / held / approved):",
    ]
    for ft in ("bustout", "takeover", "mule", "structuring"):
        sub = [r for r in fraud if r.fraud_type == ft]
        held = len(by(sub, Route.PENDING_REVIEW)) + len(by(sub, Route.FAST_HUMAN_LANE))
        out.append(f"  {ft:12s} {len(by(sub, Route.BLOCK)):3d} / {held:3d} / {len(by(sub, Route.APPROVE)):3d}  (n={len(sub)})")
    old = [r for r in fraud if r.features.account_age_days >= 90]
    out.append(f"\nfraud payouts on accounts 90+ days old: {len(old)} of {len(fraud)}")
    return "\n".join(out)


if __name__ == "__main__":
    print(summarise(replay(read_dataset())))
