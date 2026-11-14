"""The routing table. Exhaustive, first match wins (decision D-009).

    Gate 0 hit, top-200 merchant           -> FAST_HUMAN_LANE
    Gate 0 hit, anyone else                -> BLOCK
    score 0.82 or above, top-200 merchant  -> FAST_HUMAN_LANE
    score 0.82 or above                    -> BLOCK
    score 0.45 up to 0.82                  -> PENDING_REVIEW (hold)
    below 0.45, novel payee, over $2,500   -> PENDING_REVIEW (hold)
    below 0.45 otherwise                   -> APPROVE
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from hybrid_fraud.core.config import Thresholds
from hybrid_fraud.core.reason_codes import ReasonCode
from hybrid_fraud.core.schemas import Route
from hybrid_fraud.hot_path.features import PayoutFeatures
from hybrid_fraud.hot_path.gate0_rules import gate0_hits
from hybrid_fraud.hot_path.scoring import score


class HotPathResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    payout_id: str
    route: Route
    reason_codes: list[ReasonCode]
    score: float
    evidence_trace: list[str]  # templated from real values, never written by a model
    novel_anomaly_flag: bool = False  # logged on APPROVE so the pattern can be reviewed later


def route(f: PayoutFeatures, t: Thresholds) -> HotPathResult:
    s, parts = score(f)
    hits = gate0_hits(f, t.gate0)
    score_lines = [f"score +{p.weight:.2f} {p.name}: {p.evidence}" for p in parts]
    novel = (
        f.first_time_payee
        and f.beneficiary_platform_age_hrs < t.gate0.novel_payee_platform_age_hours
    )

    def result(r: Route, codes: list[ReasonCode], lines: list[str], flag: bool = False) -> HotPathResult:
        return HotPathResult(
            payout_id=f.payout_id, route=r, reason_codes=codes, score=s,
            evidence_trace=lines, novel_anomaly_flag=flag,
        )

    if hits:
        codes = [h.code for h in hits]
        lines = [f"{h.code.value}: {h.evidence}" for h in hits]
        if f.is_top_200:
            return result(Route.FAST_HUMAN_LANE, [ReasonCode.TOP_MERCHANT_FAST_LANE, *codes], lines)
        return result(Route.BLOCK, codes, lines)

    # Every score-based decision says where the score sits against the lines, so a score of zero
    # (nothing fired) still leaves a readable reason.
    a, b = t.gate1.approve_below, t.gate1.block_at_or_above

    if s >= b:
        lines = [f"score {s:.2f} is at or above the block line {b}", *score_lines]
        if f.is_top_200:
            return result(Route.FAST_HUMAN_LANE, [ReasonCode.TOP_MERCHANT_FAST_LANE, ReasonCode.HIGH_RISK_SCORE], lines)
        return result(Route.BLOCK, [ReasonCode.HIGH_RISK_SCORE], lines)

    if s >= a:
        return result(Route.PENDING_REVIEW, [ReasonCode.GRAY_ZONE_SCORE],
                      [f"score {s:.2f} is in the gray band {a} to {b}", *score_lines])

    if novel and f.amount_usd > t.gate1.novel_anomaly_hold_over_usd:
        lines = [f"score {s:.2f} is below {a}, but the payee was first seen {f.beneficiary_platform_age_hrs:.0f} h ago "
                 f"and the amount is ${f.amount_usd:,.2f}", *score_lines]
        return result(Route.PENDING_REVIEW, [ReasonCode.NOVEL_ANOMALY_LARGE], lines)

    return result(Route.APPROVE, [ReasonCode.LOW_RISK_SCORE],
                  [f"score {s:.2f} is below the approval line {a}", *score_lines], flag=novel)
