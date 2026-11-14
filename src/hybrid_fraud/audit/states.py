"""The payout lifecycle. States only move forward; nothing ever comes back.

    (new) -> RECEIVED -> PENDING_REVIEW -> APPROVED | BLOCKED | ESCALATED
                     \\-> APPROVED | BLOCKED | ESCALATED     (decided on the hot path)

APPROVED, BLOCKED and ESCALATED are final here. A human resolving an ESCALATED
payout is a later step with its own record (not built in this prototype).
"""

from __future__ import annotations

from hybrid_fraud.core.schemas import PayoutState as S

ALLOWED: dict[S | None, set[S]] = {
    None: {S.RECEIVED},
    S.RECEIVED: {S.PENDING_REVIEW, S.APPROVED, S.BLOCKED, S.ESCALATED},
    S.PENDING_REVIEW: {S.APPROVED, S.BLOCKED, S.ESCALATED},
    S.APPROVED: set(),
    S.BLOCKED: set(),
    S.ESCALATED: set(),
}


class IllegalTransition(Exception):
    pass


def check_transition(old: S | None, new: S) -> None:
    if new not in ALLOWED[old]:
        raise IllegalTransition(f"{old.value if old else 'new'} -> {new.value} is not allowed")
