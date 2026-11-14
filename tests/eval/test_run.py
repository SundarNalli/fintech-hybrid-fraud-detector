import pytest

from hybrid_fraud.core.schemas import PayoutState as S
from hybrid_fraud.eval.report import render
from hybrid_fraud.eval.run import evaluate, main
from hybrid_fraud.eval.scripted_investigator import ScriptedInvestigator


@pytest.fixture(scope="module")
def result(dataset, thresholds):
    return evaluate(dataset, lambda: ScriptedInvestigator(fault_rate=0.3), thresholds, repeats=2)


def test_all_three_systems_score_the_same_20000_payouts(result):
    ids = [sorted(r.payout_id for r in rows) for rows in result.systems.values()]
    assert len(ids[0]) == 20000 and ids[0] == ids[1] == ids[2]


def test_nothing_is_left_pending_in_any_system(result):
    assert all(r.state != S.PENDING_REVIEW for rows in result.systems.values() for r in rows)


def test_payouts_the_rules_decided_are_identical_in_all_three_systems(result):
    a, b, c = (sorted(rows, key=lambda r: r.payout_id) for rows in result.systems.values())
    same = [(x.state, y.state, z.state) for x, y, z in zip(a, b, c) if not x.was_gray]
    assert all(s[0] == s[1] == s[2] for s in same)


def test_with_no_agent_every_held_payout_goes_to_a_human(result):
    rules_only = result.systems["A rules only"]
    assert all(r.state == S.ESCALATED for r in rules_only if r.was_gray)


def test_even_with_30_percent_faults_no_decision_rests_on_an_ungrounded_claim(result):
    assert result.outcomes and any(o.claims_ungrounded for o in result.outcomes)  # faults really happened
    assert [o for o in result.outcomes if o.claims_ungrounded and not o.verifier_rejected] == []
    assert all(o.final_state == S.ESCALATED for o in result.outcomes if o.verifier_rejected)


def test_the_script_never_approves_more_than_the_policy_wrapper_allows(result, thresholds):
    cap = thresholds.agent.ai_approval_cap_usd
    approved_gray = [r for r in result.systems["B rules + agent"] if r.was_gray and r.state == S.APPROVED]
    assert all(r.amount_usd < cap for r in approved_gray)


def test_repeating_a_deterministic_script_gives_the_same_answers(result):
    assert result.repeat_agreement == 1.0


def test_the_report_says_plainly_when_the_agent_is_a_script(result, thresholds):
    text = render(result, "SCRIPTED STAND-IN (not a model), fault rate 30%", "2026-11-14", thresholds)
    assert "not a model" in text and "Decisions built on an ungrounded claim | 0 (must be 0)" in text


def test_live_mode_refuses_without_a_key_without_prices_and_without_confirm(monkeypatch):
    for var in ("OPENROUTER_API_KEY", "LLM_API_KEY", "LLM_INPUT_USD_PER_MTOK", "LLM_OUTPUT_USD_PER_MTOK"):
        monkeypatch.delenv(var, raising=False)
    assert main(["--provider", "live", "--confirm"]) == 2  # no key
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")
    assert main(["--provider", "live", "--confirm"]) == 2  # no prices, so spend cannot be metered
    monkeypatch.setenv("LLM_INPUT_USD_PER_MTOK", "1")
    monkeypatch.setenv("LLM_OUTPUT_USD_PER_MTOK", "1")
    assert main(["--provider", "live"]) == 2  # key and prices, but not confirmed: nothing is sent
