"""Checks the agent's recommendation against the records it was given.

This is the ONLY module allowed to build a `VerifiedRecommendation`; a test
enforces it. The policy wrapper accepts nothing else, so an unchecked claim
can never reach a decision.
"""

from __future__ import annotations

from hybrid_fraud.core.schemas import (
    EvidenceRecord,
    Recommendation,
    VerifiedRecommendation,
)
from hybrid_fraud.guard.hard_facts import HardFact, triggered
from hybrid_fraud.guard.predicates import holds

VERIFIER_VERSION = "1"


class VerificationError(Exception):
    """Raised when a recommendation is rejected. `failures` lists every reason."""

    def __init__(self, failures: list[str]) -> None:
        super().__init__("; ".join(failures))
        self.failures = failures


def verify(
    recommendation: Recommendation,
    evidence_records: list[EvidenceRecord],
    payout_id: str,
    hard_facts: tuple[HardFact, ...],
) -> VerifiedRecommendation:
    # Only records fetched for THIS case count; an ID from elsewhere is a fabrication.
    by_id = {r.evidence_id: r for r in evidence_records}
    failures: list[str] = []

    for claim in recommendation.claims:
        record = by_id.get(claim.evidence_id)
        if record is None:
            failures.append(f"unknown evidence_id {claim.evidence_id!r} (not fetched for this case)")
        elif not holds(record.fields, claim.field, claim.op, claim.value):
            failures.append(
                f"claim false: {claim.evidence_id}.{claim.field} {claim.op} {claim.value!r} "
                f"(actual {record.fields.get(claim.field, '<missing>')!r})"
            )

    # Collect every contradiction so the audit trail shows the whole picture.
    for fact in triggered(hard_facts, evidence_records):
        if recommendation.action in fact.forbids:
            failures.append(f"{recommendation.action} contradicts hard fact {fact.name!r}")

    if failures:
        raise VerificationError(failures)

    return VerifiedRecommendation(
        payout_id=payout_id,
        action=recommendation.action,
        reason_codes=list(recommendation.reason_codes),
        claims=list(recommendation.claims),
        narrative=recommendation.narrative,
        evidence=list(evidence_records),
        verifier_version=VERIFIER_VERSION,
    )
