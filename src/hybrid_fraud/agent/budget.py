"""Budget meter: dollars, tool calls and seconds, checked after every step.

Prices are passed in, never hard-coded: model prices change, and this repo
should not carry a stale table.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from hybrid_fraud.core.config import Agent


@dataclass(frozen=True)
class Prices:
    """US dollars per single token."""

    input_per_token: float = 0.0
    output_per_token: float = 0.0


class BudgetMeter:
    def __init__(self, limits: Agent, prices: Prices, clock: Callable[[], float] = time.monotonic):
        self.limits, self.prices, self._clock = limits, prices, clock
        self._start = clock()
        self.usd = 0.0
        self.tool_calls = 0

    @property
    def elapsed(self) -> float:
        return self._clock() - self._start

    def remaining_seconds(self) -> float:
        return max(0.0, self.limits.timeout_seconds - self.elapsed)

    def add_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.usd += prompt_tokens * self.prices.input_per_token
        self.usd += completion_tokens * self.prices.output_per_token

    def allow_tool_call(self) -> bool:
        """Count a tool call, or refuse it if the cap is already reached."""
        if self.tool_calls >= self.limits.max_tool_calls:
            return False
        self.tool_calls += 1
        return True

    def exceeded(self) -> str | None:
        """A reason code if time or money ran out, else None."""
        if self.elapsed > self.limits.timeout_seconds:
            return "agent_timeout"
        if self.usd > self.limits.max_usd_per_case:
            return "agent_over_budget"
        return None
