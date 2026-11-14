"""Gate 0: hard rules on facts that cannot be argued away and cannot be undone.

A false block here is permanent and visible, so each rule fires on a
coincidence of facts, not on one fact. Every hit carries an evidence line built
from the real values, by template, never by a model.
"""

from __future__ import annotations

from dataclasses import dataclass

from hybrid_fraud.core.config import Gate0
from hybrid_fraud.core.reason_codes import ReasonCode
from hybrid_fraud.hot_path.features import PayoutFeatures


@dataclass(frozen=True)
class RuleHit:
    code: ReasonCode
    evidence: str


def gate0_hits(f: PayoutFeatures, t: Gate0) -> list[RuleHit]:
    hits: list[RuleHit] = []

    # A brand-new account paying a brand-new payee a large sum that cannot be recalled.
    if (
        f.account_age_days < t.new_account_days
        and f.beneficiary_age_hrs < t.new_payee_hours
        and f.amount_usd > t.large_amount_usd
    ):
        hits.append(RuleHit(
            ReasonCode.NEW_ACCOUNT_NEW_PAYEE_LARGE,
            f"account is {f.account_age_days:.0f} days old, payee added {f.beneficiary_age_hrs:.1f} h ago, "
            f"amount ${f.amount_usd:,.2f}",
        ))

    # One device driving several businesses is not a business.
    if f.shared_device_merchants >= t.shared_device_min_merchants and f.account_age_days < t.young_account_days:
        hits.append(RuleHit(
            ReasonCode.DEVICE_SHARED_ACROSS_MERCHANTS,
            f"device is linked to {f.shared_device_merchants} merchants, account is {f.account_age_days:.0f} days old",
        ))

    # A payout far beyond anything this young account has processed.
    if (
        f.avg_daily_volume_30d > 0
        and f.amount_usd > t.amount_multiple_of_daily_volume * f.avg_daily_volume_30d
        and f.account_age_days < t.young_account_days
    ):
        hits.append(RuleHit(
            ReasonCode.AMOUNT_MULTIPLE_OF_HISTORY,
            f"amount ${f.amount_usd:,.2f} is {f.amount_usd / f.avg_daily_volume_30d:.1f}x the "
            f"${f.avg_daily_volume_30d:,.2f} daily average",
        ))

    # Closes the $2,500 loophole: many small payouts that add up within an hour.
    if (
        f.velocity_count_1h >= t.structuring_min_count_1h
        and f.velocity_usd_1h >= t.structuring_usd_1h
        and f.velocity_usd_1h > t.structuring_multiple_of_daily_volume * f.avg_daily_volume_30d
    ):
        hits.append(RuleHit(
            ReasonCode.DOLLAR_VELOCITY_STRUCTURING,
            f"{f.velocity_count_1h} payouts totalling ${f.velocity_usd_1h:,.2f} in one hour, "
            f"against a ${f.avg_daily_volume_30d:,.2f} daily average",
        ))

    # A new payee fed by many unrelated merchants: the shape of a mule account.
    if (
        f.beneficiary_distinct_merchants_24h >= t.mule_beneficiary_min_merchants_24h
        and f.beneficiary_platform_age_hrs < t.mule_beneficiary_max_platform_age_hours
    ):
        hits.append(RuleHit(
            ReasonCode.BENEFICIARY_FED_BY_MANY_MERCHANTS,
            f"payee received from {f.beneficiary_distinct_merchants_24h} merchants in 24 h "
            f"and was first seen {f.beneficiary_platform_age_hrs:.1f} h ago",
        ))

    if f.beneficiary_on_mule_list:
        hits.append(RuleHit(ReasonCode.BENEFICIARY_ON_MULE_LIST, "payee is on the known mule list"))

    return hits
