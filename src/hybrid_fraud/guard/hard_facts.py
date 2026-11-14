"""Facts that no AI narrative may argue with.

Each hard fact is a predicate over an evidence field plus the actions it
forbids. The list is data, so it can change without touching the verifier.
"""

from __future__ import annotations

from dataclasses import dataclass

from hybrid_fraud.core.schemas import AgentAction, EvidenceRecord, Scalar
from hybrid_fraud.guard.predicates import holds


@dataclass(frozen=True)
class HardFact:
    name: str
    field: str
    op: str
    value: Scalar
    forbids: frozenset[AgentAction]


_NO_APPROVE = frozenset({AgentAction.APPROVE})

DEFAULT_HARD_FACTS: tuple[HardFact, ...] = (
    HardFact("2fa_ticket_last_48h", "has_2fa_ticket_48h", "eq", True, _NO_APPROVE),
    HardFact("credential_ticket", "has_credential_ticket_48h", "eq", True, _NO_APPROVE),
    HardFact("beneficiary_on_mule_list", "on_mule_list", "eq", True, _NO_APPROVE),
    HardFact("mule_flagged_neighbours", "mule_flagged_neighbors", "gt", 0, _NO_APPROVE),
)


def triggered(hard_facts: tuple[HardFact, ...], records: list[EvidenceRecord]) -> list[HardFact]:
    """Hard facts that are true in at least one of the supplied records."""
    return [
        fact
        for fact in hard_facts
        if any(holds(r.fields, fact.field, fact.op, fact.value) for r in records)
    ]
