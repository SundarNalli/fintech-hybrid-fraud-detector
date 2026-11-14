from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from agent_fake_repo import INJECTION, FakeRepo, make_payout
from hybrid_fraud.agent.budget import Prices
from hybrid_fraud.agent.orchestrator import run_case
from hybrid_fraud.agent.providers import (
    OpenAICompatibleProvider, ProviderError, ProviderResponse, ReplayProvider, ToolCall, make_provider,
)
from hybrid_fraud.agent.tools import ToolBox, tool_definitions
from hybrid_fraud.core.config import load_thresholds
from hybrid_fraud.core.schemas import AgentAction

FIXTURES = Path(__file__).parent / "fixtures"
LIMITS = load_thresholds().agent
PRICES = Prices(input_per_token=1e-6, output_per_token=2e-6)


def run(case_id, provider=None, **kw):
    provider = provider or ReplayProvider(FIXTURES)
    return run_case(make_payout(case_id, **kw.pop("payout", {})), provider, FakeRepo(), LIMITS, PRICES, **kw)


class Scripted:
    """Provider that keeps asking for the same tool, optionally slowly."""

    def __init__(self, tick=None):
        self.tick, self.calls = tick, 0

    def complete(self, messages, tools, *, case_id, temperature=0.0, timeout=None):
        self.calls += 1
        if self.tick:
            self.tick()
        return ProviderResponse(tool_calls=[ToolCall(name="merchant_profile")])


def test_loop_stops_at_4_tool_calls():
    provider = Scripted()
    result = run("p_any", provider)
    assert result.tool_calls == 4 == LIMITS.max_tool_calls
    assert provider.calls == 5  # the fifth request is refused, not served
    assert result.recommendation.action is AgentAction.ESCALATE_HUMAN
    assert result.stop_reason == "agent_tool_call_limit"


def test_timeout_gives_escalate_human():
    now = [0.0]
    result = run("p_any", Scripted(tick=lambda: now.__setitem__(0, now[0] + 9)), clock=lambda: now[0])
    assert result.recommendation.action is AgentAction.ESCALATE_HUMAN
    assert result.stop_reason == "agent_timeout"


def test_malformed_output_gives_escalate_human():
    result = run("p_malformed")
    assert result.recommendation.action is AgentAction.ESCALATE_HUMAN
    assert result.stop_reason == "agent_malformed_output"


def test_over_budget_gives_escalate_human():
    pricey = Prices(input_per_token=1.0)  # one dollar per token
    result = run_case(make_payout("p_approve"), ReplayProvider(FIXTURES), FakeRepo(), LIMITS, pricey)
    assert result.stop_reason == "agent_over_budget"
    assert result.recommendation.action is AgentAction.ESCALATE_HUMAN


def test_missing_recording_is_a_provider_error_not_an_approval():
    result = run("p_unknown")
    assert result.stop_reason == "agent_provider_error"
    assert result.recommendation.action is AgentAction.ESCALATE_HUMAN


def test_approve_with_real_evidence_returns_the_records_it_cites():
    result = run("p_approve")
    ids = {e.evidence_id for e in result.evidence}
    assert result.recommendation.action is AgentAction.APPROVE
    assert {c.evidence_id for c in result.recommendation.claims} <= ids


def test_block_and_escalate_recordings_are_returned_as_recorded():
    assert run("p_block").recommendation.action is AgentAction.BLOCK
    assert run("p_escalate").recommendation.action is AgentAction.ESCALATE_HUMAN


def test_a_cited_nonexistent_evidence_id_is_passed_through_for_the_guard_to_reject():
    result = run("p_fake_evidence")
    cited = result.recommendation.claims[0].evidence_id
    assert cited not in {e.evidence_id for e in result.evidence}


def test_injected_text_is_fenced_in_every_message_and_marked_merchant_authored():
    result = run("p_injected", payout={"memo": INJECTION})
    sent = "\n".join(str(m["content"]) for m in result.messages)
    assert "<<<UNTRUSTED_DATA payout_memo>>>" in sent and "<<<UNTRUSTED_DATA kyb_text>>>" in sent
    assert ">>> END" not in sent  # the attacker's own fence marker was neutralised
    assert "kyb_text" in result.evidence[0].merchant_authored


def test_cost_and_call_count_are_reported_per_case():
    result = run("p_approve")
    assert result.tool_calls == 3
    assert result.cost_usd == pytest.approx(4 * (1000 * 1e-6 + 100 * 2e-6))
    assert result.latency_seconds >= 0


def test_no_key_falls_back_to_replay():
    assert isinstance(make_provider(FIXTURES, env={}), ReplayProvider)
    assert isinstance(make_provider(FIXTURES, env={"LLM_API_KEY": "  "}), ReplayProvider)
    assert isinstance(make_provider(FIXTURES, env={"LLM_API_KEY": "k"}), OpenAICompatibleProvider)
    assert isinstance(make_provider(FIXTURES, env={"OPENROUTER_API_KEY": "k"}), OpenAICompatibleProvider)


def test_the_key_never_appears_in_repr_or_logs(caplog):
    key = "sk-super-secret-123"
    provider = OpenAICompatibleProvider(
        SecretStr(key), "m", client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500))))
    with caplog.at_level("DEBUG"), pytest.raises(ProviderError) as err:
        provider.complete([], [], case_id="x")
    assert key not in repr(provider) and key not in str(err.value) and key not in caplog.text
    assert key not in repr(provider.__dict__)


def test_openai_compatible_provider_parses_tool_calls_and_usage():
    body = {"choices": [{"message": {"content": None, "tool_calls": [
        {"id": "a", "function": {"name": "entity_graph", "arguments": "{}"}}]}}],
        "usage": {"prompt_tokens": 7, "completion_tokens": 3}}
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body)))
    resp = OpenAICompatibleProvider(SecretStr("k"), "m", client=client).complete([], [], case_id="x")
    assert resp.tool_calls[0].name == "entity_graph" and resp.usage.prompt_tokens == 7


def test_tools_expose_no_write_method():
    names = [d["function"]["name"] for d in tool_definitions()]
    assert names == ["merchant_profile", "entity_graph", "support_tickets", "beneficiary_history",
                     "submit_recommendation"]
    public = [n for n in dir(ToolBox(FakeRepo(), "m_1", "b_1")) if not n.startswith("_")]
    assert sorted(public) == ["names", "run"]
    assert not any(w in n for n in dir(FakeRepo()) for w in ("write", "insert", "update", "delete", "set_"))
