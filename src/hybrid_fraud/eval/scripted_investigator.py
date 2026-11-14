"""A scripted stand-in for the model. It is NOT a model, and nothing it scores says anything about one.

It exists to run the whole pipeline (tools, verifier, policy wrapper, ledger) end to end,
offline and for free, and to test the guard under controlled mistakes. It reads the same
tool-result text a model would see, and follows a fixed rule:

    any hard signal (credential or 2FA ticket, mule payee, mule-flagged neighbour)  -> BLOCK
    payee paid by 20+ merchants with 20+ settled payouts, clean graph               -> APPROVE
    anything else                                                                  -> ESCALATE_HUMAN

`fault_rate` makes it deliberately wrong on a fixed share of cases (chosen by hashing the case
id, so runs repeat exactly): half cite an evidence record that does not exist, half state a
false value. That measures whether the verifier catches what a careless model would do.
"""

from __future__ import annotations

import hashlib
import json

from hybrid_fraud.agent.providers import ProviderResponse, ToolCall, Usage

EVIDENCE_TOOLS = ["merchant_profile", "entity_graph", "support_tickets", "beneficiary_history"]


def parse_evidence(text: str) -> tuple[str, dict]:
    """Read back a rendered tool result: plain `key: value` lines; fenced merchant text is skipped."""
    eid, fields, fenced = "", {}, False
    for line in text.splitlines():
        if line.startswith("<<<END_UNTRUSTED_DATA"):
            fenced = False
        elif fenced:
            continue
        elif line.startswith("<<<UNTRUSTED_DATA"):
            fenced = True
        elif line.startswith("evidence_id: "):
            eid = line.split(": ", 1)[1]
        elif ": " in line:
            k, v = line.split(": ", 1)
            fields[k] = {"True": True, "False": False, "None": None}.get(v, _number(v))
    return eid, fields


def _number(v: str):
    for cast in (int, float):
        try:
            return cast(v)
        except ValueError:
            pass
    return v


class ScriptedInvestigator:
    def __init__(self, fault_rate: float = 0.0):
        self.fault_rate = fault_rate

    def complete(self, messages, tools, *, case_id, temperature=0.0, timeout=None) -> ProviderResponse:
        tool_msgs = [m for m in messages if m["role"] == "tool"]
        chars = sum(len(str(m.get("content") or "")) for m in messages)
        usage = Usage(prompt_tokens=chars // 4, completion_tokens=60)
        if not tool_msgs:
            calls = [ToolCall(id=f"call_{i}", name=n) for i, n in enumerate(EVIDENCE_TOOLS)]
            return ProviderResponse(tool_calls=calls, usage=usage)
        records = dict(parse_evidence(m["content"]) for m in tool_msgs)
        rec = self._decide(records)
        rec = self._maybe_fault(rec, case_id)
        return ProviderResponse(tool_calls=[ToolCall(name="submit_recommendation", arguments=json.dumps(rec))],
                                usage=usage)

    @staticmethod
    def _claim(eid, field, op, value, kind):
        return {"field": field, "op": op, "value": value, "evidence_id": eid, "kind": kind}

    def _decide(self, records: dict) -> dict:
        def find(prefix):
            return next(((e, f) for e, f in records.items() if e.startswith(prefix)), (None, {}))

        _, _ = find("merchant_profile")
        g_id, graph = find("entity_graph")
        t_id, tix = find("support_tickets")
        b_id, bene = find("beneficiary_history")

        hard = []
        if tix.get("has_credential_ticket_48h") is True:
            hard.append(self._claim(t_id, "has_credential_ticket_48h", "eq", True, "hard_signal"))
        if tix.get("has_2fa_ticket_48h") is True:
            hard.append(self._claim(t_id, "has_2fa_ticket_48h", "eq", True, "hard_signal"))
        if (graph.get("mule_flagged_neighbors") or 0) > 0:
            hard.append(self._claim(g_id, "mule_flagged_neighbors", "gt", 0, "hard_signal"))
        if bene.get("on_mule_list") is True:
            hard.append(self._claim(b_id, "on_mule_list", "eq", True, "hard_signal"))
        if hard:
            return {"action": "BLOCK", "reason_codes": ["scripted_hard_signal"], "claims": hard}

        if ((bene.get("distinct_merchants_30d") or 0) >= 20 and (bene.get("settled_payouts_30d") or 0) >= 20
                and graph.get("graph_clean") is True):
            return {"action": "APPROVE", "reason_codes": ["scripted_established_payee"], "claims": [
                self._claim(b_id, "distinct_merchants_30d", "gte", 20, "positive"),
                self._claim(b_id, "settled_payouts_30d", "gte", 20, "positive"),
                self._claim(g_id, "graph_clean", "eq", True, "positive")]}

        return {"action": "ESCALATE_HUMAN", "reason_codes": ["scripted_no_clear_answer"], "claims": []}

    def _maybe_fault(self, rec: dict, case_id: str) -> dict:
        if not rec["claims"] or self.fault_rate <= 0:
            return rec
        h = int(hashlib.sha256(case_id.encode()).hexdigest(), 16)
        if (h % 1000) / 1000 >= self.fault_rate:
            return rec
        claims = [dict(c) for c in rec["claims"]]
        if (h // 1000) % 2 == 0:  # cite a record that was never fetched
            claims[0]["evidence_id"] = "merchant_profile:m_never_fetched"
        else:  # state something false about a real record
            v = claims[0]["value"]
            claims[0]["value"] = (not v) if isinstance(v, bool) else v + 1_000_000
        return {**rec, "claims": claims}
