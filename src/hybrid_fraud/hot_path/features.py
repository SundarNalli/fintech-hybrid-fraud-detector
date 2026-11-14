"""What the hot path knows about a payout at the moment it arrives.

Everything here is known at payout time. Fraud labels and later outcomes are
never part of it (see "known at payout time versus learned later").
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from hybrid_fraud.core.schemas import Payout
from hybrid_fraud.hot_path.velocity import VelocitySnapshot


class PayoutFeatures(BaseModel):
    model_config = ConfigDict(frozen=True)

    payout_id: str
    merchant_id: str
    amount_usd: float
    is_top_200: bool

    account_age_days: float
    avg_daily_volume_30d: float
    chargeback_rate_90d: float

    beneficiary_age_hrs: float  # since this merchant added the payee
    beneficiary_platform_age_hrs: float  # since anyone on the platform first paid them
    beneficiary_on_mule_list: bool
    first_time_payee: bool  # this merchant has never paid them before

    shared_device_merchants: int  # merchants linked to this device, including this one
    support_2fa_ticket_48h: bool
    support_credential_ticket_48h: bool

    # Velocity windows include the payout being scored: "the totals if we approve it".
    velocity_count_1h: int
    velocity_usd_1h: float
    velocity_usd_24h: float
    beneficiary_distinct_merchants_24h: int
    beneficiary_usd_24h: float


class FeatureLookup(Protocol):
    """Static facts the hot path reads. The SQLite version arrives in Phase 2."""

    def account_age_days(self, merchant_id: str, at: datetime) -> float: ...
    def merchant_stats(self, merchant_id: str) -> tuple[float, float, bool]:
        """(avg_daily_volume_30d, chargeback_rate_90d, is_top_200)"""
        ...

    def beneficiary_facts(self, merchant_id: str, beneficiary_id: str, at: datetime) -> tuple[float, float, bool]:
        """(hours since merchant added payee, hours since platform first saw payee, on_mule_list)"""
        ...

    def shared_device_merchants(self, device_id: str, at: datetime) -> int: ...
    def recent_ticket_flags(self, merchant_id: str, at: datetime) -> tuple[bool, bool]:
        """(2FA ticket in last 48 h, credential ticket in last 48 h)"""
        ...


def build_features(payout: Payout, lookup: FeatureLookup, velocity: VelocitySnapshot) -> PayoutFeatures:
    avg_daily, chargeback, top = lookup.merchant_stats(payout.merchant_id)
    payee_age, platform_age, on_mule = lookup.beneficiary_facts(
        payout.merchant_id, payout.beneficiary_id, payout.created_at
    )
    t2fa, tcred = lookup.recent_ticket_flags(payout.merchant_id, payout.created_at)
    return PayoutFeatures(
        payout_id=payout.payout_id,
        merchant_id=payout.merchant_id,
        amount_usd=payout.amount_usd,
        is_top_200=top,
        account_age_days=lookup.account_age_days(payout.merchant_id, payout.created_at),
        avg_daily_volume_30d=avg_daily,
        chargeback_rate_90d=chargeback,
        beneficiary_age_hrs=payee_age,
        beneficiary_platform_age_hrs=platform_age,
        beneficiary_on_mule_list=on_mule,
        first_time_payee=velocity.first_time_payee,
        shared_device_merchants=lookup.shared_device_merchants(payout.device_id, payout.created_at),
        support_2fa_ticket_48h=t2fa,
        support_credential_ticket_48h=tcred,
        velocity_count_1h=velocity.count_1h,
        velocity_usd_1h=velocity.usd_1h,
        velocity_usd_24h=velocity.usd_24h,
        beneficiary_distinct_merchants_24h=velocity.beneficiary_distinct_merchants_24h,
        beneficiary_usd_24h=velocity.beneficiary_usd_24h,
    )
