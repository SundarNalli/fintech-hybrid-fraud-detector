"""Gate 1: a score from named contributions, so any number can be explained.

There is no fitted model on purpose. The first question is how much can be
decided without one. If a fitted model is needed later, this score is the
baseline it has to beat. Every weight is a judgement that can be argued with.
"""

from __future__ import annotations

from dataclasses import dataclass

from hybrid_fraud.hot_path.features import PayoutFeatures


@dataclass(frozen=True)
class ScorePart:
    name: str
    weight: float
    evidence: str


def score(f: PayoutFeatures) -> tuple[float, list[ScorePart]]:
    parts: list[ScorePart] = []

    def add(name: str, weight: float, evidence: str) -> None:
        parts.append(ScorePart(name, weight, evidence))

    if f.account_age_days < 30:
        add("account_age<30", 0.30, f"account is {f.account_age_days:.0f} days old")
    elif f.account_age_days < 90:
        add("account_age<90", 0.15, f"account is {f.account_age_days:.0f} days old")

    if f.beneficiary_age_hrs < 6:
        add("payee_age<6h", 0.25, f"payee added {f.beneficiary_age_hrs:.1f} h ago")
    elif f.beneficiary_age_hrs < 48:
        add("payee_age<48h", 0.10, f"payee added {f.beneficiary_age_hrs:.1f} h ago")

    if f.shared_device_merchants >= 3:
        add("shared_device>=3", 0.15, f"device linked to {f.shared_device_merchants} merchants")

    if f.avg_daily_volume_30d > 0:
        ratio = f.amount_usd / f.avg_daily_volume_30d
        if ratio > 5:
            add("amount>5x_avg", 0.20, f"amount is {ratio:.1f}x the daily average")
        elif ratio > 2:
            add("amount>2x_avg", 0.08, f"amount is {ratio:.1f}x the daily average")
        # Dollar velocity: the same idea over a day, in dollars, not just count.
        day_ratio = f.velocity_usd_24h / f.avg_daily_volume_30d
        if day_ratio > 5:
            add("dollars_24h>5x_avg", 0.15, f"${f.velocity_usd_24h:,.2f} in 24 h is {day_ratio:.1f}x the daily average")

    if f.velocity_count_1h >= 5:
        add("velocity>=5", 0.10, f"{f.velocity_count_1h} payouts in the last hour")

    if f.beneficiary_distinct_merchants_24h >= 3 and f.beneficiary_platform_age_hrs < 168:
        add("new_payee_fed_by_3+", 0.20,
            f"payee fed by {f.beneficiary_distinct_merchants_24h} merchants, first seen "
            f"{f.beneficiary_platform_age_hrs:.0f} h ago")

    if f.chargeback_rate_90d > 0.02:
        add("chargeback>2%", 0.10, f"chargeback rate {f.chargeback_rate_90d:.1%}")

    if f.support_2fa_ticket_48h:
        add("2fa_ticket_48h", 0.12, "a two-factor ticket was opened in the last 48 h")

    total = round(min(sum(p.weight for p in parts), 1.0), 4)
    return total, parts
