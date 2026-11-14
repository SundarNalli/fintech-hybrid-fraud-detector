"""The tables of the synthetic world. Everything here is invented.

The hot path may read every table except `Label`. Labels (the truth, and what
we only learn later) are kept apart so the service never sees them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from hybrid_fraud.core.schemas import Payout


class _Row(BaseModel):
    model_config = ConfigDict(frozen=True)


class Merchant(_Row):
    merchant_id: str
    created_at: datetime
    legal_name: str
    sector: str
    mcc_code: str
    avg_daily_volume_30d: float
    chargeback_rate_90d: float
    is_top_200: bool
    kyb_text: str  # merchant-authored: attacker-controlled


class Beneficiary(_Row):
    beneficiary_id: str
    name: str
    first_seen_at: datetime  # first time anyone on the platform paid them
    on_mule_list: bool


class BeneficiaryLink(_Row):
    """A merchant adding a payee. The age of this link is the payee's age for them."""

    merchant_id: str
    beneficiary_id: str
    added_at: datetime


class DeviceLink(_Row):
    """A merchant account seen logging in from a device. Only counts once `first_seen_at` has passed."""

    merchant_id: str
    device_id: str
    first_seen_at: datetime


class Ticket(_Row):
    ticket_id: str
    merchant_id: str
    created_at: datetime
    category: Literal["2fa", "credential", "billing", "other"]
    text: str  # merchant-authored: attacker-controlled


FraudType = Literal["bustout", "takeover", "mule", "structuring"]


class Label(_Row):
    """Ground truth. Never read by the service; only by the evaluation."""

    payout_id: str
    is_fraud: bool
    fraud_type: FraudType | None = None


class Dataset(_Row):
    seed: int
    noise: float
    merchants: list[Merchant]
    beneficiaries: list[Beneficiary]
    beneficiary_links: list[BeneficiaryLink]
    device_links: list[DeviceLink]
    tickets: list[Ticket]
    payouts: list[Payout]
    labels: list[Label]
