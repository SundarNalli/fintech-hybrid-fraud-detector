from hybrid_fraud.agent.prompt import render_evidence
from hybrid_fraud.eval.scripted_investigator import ScriptedInvestigator, parse_evidence
from hybrid_fraud.sim.scenarios import scenarios


def test_the_scripted_reader_recovers_trusted_fields_and_skips_fenced_merchant_text():
    rec = next(s for s in scenarios() if s.name.startswith("3")).evidence[2]  # support tickets
    eid, fields = parse_evidence(render_evidence(rec))
    assert eid == "support_tickets:sc3_m"
    assert fields["has_credential_ticket_48h"] is True and fields["ticket_count_48h"] == 1
    assert "ticket_text" not in fields  # merchant-written text never reaches the decision


def test_a_credential_ticket_makes_the_script_block_with_a_hard_signal_claim():
    sc = next(s for s in scenarios() if s.name.startswith("3"))
    records = dict(parse_evidence(render_evidence(r)) for r in sc.evidence)
    rec = ScriptedInvestigator()._decide(records)
    assert rec["action"] == "BLOCK" and rec["claims"][0]["kind"] == "hard_signal"


def test_an_established_payee_with_a_clean_graph_makes_the_script_approve_on_two_trusted_fields():
    sc = next(s for s in scenarios() if s.name.startswith("4"))
    rec = ScriptedInvestigator()._decide(dict(parse_evidence(render_evidence(r)) for r in sc.evidence))
    assert rec["action"] == "APPROVE" and len(rec["claims"]) == 3


def test_thin_evidence_makes_the_script_escalate_with_no_claims():
    sc = next(s for s in scenarios() if s.name.startswith("1"))  # a brand-new payee nobody else pays
    rec = ScriptedInvestigator()._decide(dict(parse_evidence(render_evidence(r)) for r in sc.evidence))
    assert rec["action"] == "ESCALATE_HUMAN" and rec["claims"] == []


def test_fault_injection_is_repeatable_and_only_touches_cases_that_have_claims():
    sc = next(s for s in scenarios() if s.name.startswith("3"))
    records = dict(parse_evidence(render_evidence(r)) for r in sc.evidence)
    bot = ScriptedInvestigator(fault_rate=1.0)
    clean = ScriptedInvestigator()._decide(records)
    a, b = bot._maybe_fault(clean, "case_1"), bot._maybe_fault(clean, "case_1")
    assert a == b and a != clean
    assert bot._maybe_fault({"claims": [], "action": "ESCALATE_HUMAN"}, "x")["claims"] == []
