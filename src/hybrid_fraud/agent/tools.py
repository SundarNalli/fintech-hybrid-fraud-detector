"""The agent's four read-only tools.

A toolbox is built for ONE payout and takes no arguments from the model. The
model cannot ask about other merchants, so a confused or manipulated model has
nothing else to look at. The repository protocol has no write methods, so no
tool here can change anything.
"""

from __future__ import annotations

from collections.abc import Callable

from hybrid_fraud.core.repository import ReadOnlyRepository
from hybrid_fraud.core.schemas import EvidenceRecord, Recommendation

SUBMIT = "submit_recommendation"

_DESCRIPTIONS = {
    "merchant_profile": "Merchant age, sector, volume, chargeback rate, KYB text.",
    "entity_graph": "2-hop neighbourhood: shared devices, linked merchants, mule neighbours.",
    "support_tickets": "Support tickets from the last 48 hours (2FA or credential requests).",
    "beneficiary_history": "How old the beneficiary is and how many merchants paid it.",
}


def _definition(name: str, description: str, parameters: dict) -> dict:
    # OpenAI "function" format: the de facto standard that OpenRouter also speaks.
    return {"type": "function", "function": {"name": name, "description": description, "parameters": parameters}}


def tool_definitions() -> list[dict]:
    no_args = {"type": "object", "properties": {}}
    evidence_tools = [_definition(n, d, no_args) for n, d in _DESCRIPTIONS.items()]
    submit = _definition(
        SUBMIT,
        "Give your final recommendation. Every claim must cite an evidence_id you received.",
        Recommendation.model_json_schema(),
    )
    return [*evidence_tools, submit]


class ToolBox:
    def __init__(self, repo: ReadOnlyRepository, merchant_id: str, beneficiary_id: str):
        self.names: dict[str, Callable[[], EvidenceRecord]] = {
            "merchant_profile": lambda: repo.merchant_profile(merchant_id),
            "entity_graph": lambda: repo.entity_graph(merchant_id),
            "support_tickets": lambda: repo.support_tickets(merchant_id),
            "beneficiary_history": lambda: repo.beneficiary_history(beneficiary_id),
        }

    def run(self, name: str) -> EvidenceRecord:
        if name not in self.names:
            raise KeyError(f"unknown tool: {name}")
        return self.names[name]()
