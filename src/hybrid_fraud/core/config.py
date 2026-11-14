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
    gate1: Gate1
    routing: Routing
    agent: Agent
    holds: Holds
    human_queue: HumanQueue
    latency_targets: LatencyTargets


def load_thresholds(path: Path | None = None) -> Thresholds:
    with open(path or DEFAULT_PATH, "rb") as f:
        return Thresholds.model_validate(tomllib.load(f))
