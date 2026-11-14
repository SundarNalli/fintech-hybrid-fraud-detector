"""Load config/thresholds.toml into typed, frozen settings."""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "config" / "thresholds.toml"


class _Section(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Gate1(_Section):
    approve_below: float
    block_at_or_above: float
    novel_anomaly_hold_over_usd: float


class Gate0(_Section):
    large_amount_usd: float
    new_account_days: float
    young_account_days: float
    new_payee_hours: float
    shared_device_min_merchants: int
    amount_multiple_of_daily_volume: float
    structuring_usd_1h: float
    structuring_min_count_1h: int
    structuring_multiple_of_daily_volume: float
    mule_beneficiary_min_merchants_24h: int
    mule_beneficiary_max_platform_age_hours: float
    novel_payee_platform_age_hours: float


class Routing(_Section):
    top_merchant_count: int


class Agent(_Section):
    max_tool_calls: int
    timeout_seconds: float
    max_usd_per_case: float
    temperature: float
    ai_approval_cap_usd: float


class Holds(_Section):
    deadline_seconds: float


class HumanQueue(_Section):
    escalated_response_minutes: float
    fast_lane_response_minutes: float


class LatencyTargets(_Section):
    hot_path_p99_ms: float
    gray_zone_p95_seconds: float


class Thresholds(_Section):
    gate0: Gate0
    gate1: Gate1
    routing: Routing
    agent: Agent
    holds: Holds
    human_queue: HumanQueue
    latency_targets: LatencyTargets


def load_thresholds(path: Path | None = None) -> Thresholds:
    with open(path or DEFAULT_PATH, "rb") as f:
        return Thresholds.model_validate(tomllib.load(f))
