"""The tool-call loop. Plain code, no framework (D-004).

Whatever goes wrong, the answer is ESCALATE_HUMAN, never an approval.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from pydantic import ValidationError

from hybrid_fraud.agent.budget import BudgetMeter, Prices
from hybrid_fraud.agent.prompt import SYSTEM_PROMPT, payout_message, render_evidence
from hybrid_fraud.agent.providers import LlmProvider, NoToolSupport, ProviderError
from hybrid_fraud.agent.tools import SUBMIT, ToolBox, tool_definitions
from hybrid_fraud.core.config import Agent
from hybrid_fraud.core.repository import ReadOnlyRepository
from hybrid_fraud.core.schemas import AgentAction, EvidenceRecord, Payout, Recommendation


@dataclass
class AgentResult:
    recommendation: Recommendation
    evidence: list[EvidenceRecord]  # exactly what the tools returned; the guard checks claims against these
    tool_calls: int
    cost_usd: float
    latency_seconds: float
    stop_reason: str  # "submitted", or the reason code of the escalation
    messages: list[dict] = field(default_factory=list, repr=False)


def _escalate(code: str) -> Recommendation:
    return Recommendation(action=AgentAction.ESCALATE_HUMAN, reason_codes=[code],
                          narrative=f"Agent stopped without a usable answer: {code}.")


def run_case(payout: Payout, provider: LlmProvider, repo: ReadOnlyRepository, limits: Agent,
             prices: Prices = Prices(), clock: Callable[[], float] = time.monotonic) -> AgentResult:
    meter = BudgetMeter(limits, prices, clock)
    box = ToolBox(repo, payout.merchant_id, payout.beneficiary_id)
    tools = tool_definitions()
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": payout_message(payout)}]
    evidence: list[EvidenceRecord] = []

    def finish(rec: Recommendation, why: str) -> AgentResult:
        return AgentResult(rec, evidence, meter.tool_calls, meter.usd, meter.elapsed, why, messages)

    def stop(code: str) -> AgentResult:
        return finish(_escalate(code), code)

    while True:
        try:
            resp = provider.complete(messages, tools, case_id=payout.payout_id,
                                     temperature=limits.temperature, timeout=meter.remaining_seconds())
        except NoToolSupport:
            return stop("agent_no_tool_support")
        except ProviderError:
            return stop("agent_provider_error")
        meter.add_usage(resp.usage.prompt_tokens, resp.usage.completion_tokens)
        if code := meter.exceeded():
            return stop(code)
        if not resp.tool_calls:  # prose instead of a tool call is not an answer
            return stop("agent_malformed_output")
        messages.append({"role": "assistant", "content": resp.text, "tool_calls": [
            {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}}
            for c in resp.tool_calls]})
        for call in resp.tool_calls:
            if call.name == SUBMIT:
                try:
                    return finish(Recommendation.model_validate(json.loads(call.arguments)), "submitted")
                except (ValidationError, ValueError):
                    return stop("agent_malformed_output")
            if not meter.allow_tool_call():
                return stop("agent_tool_call_limit")
            try:
                record = box.run(call.name)
            except KeyError:  # the model invented a tool name
                return stop("agent_malformed_output")
            evidence.append(record)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": render_evidence(record)})
        if code := meter.exceeded():
            return stop(code)
